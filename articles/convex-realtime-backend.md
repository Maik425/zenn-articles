---
title: "Convexを使ったらリアルタイム同期が楽すぎた - WebSocket実装なしで動く仕組み"
emoji: "⚡"
type: "tech"
topics: ["Convex", "リアルタイム", "TypeScript", "バックエンド", "React"]
published: true
---

## リアルタイム機能、毎回つらい

チャットアプリ、共同編集、ライブダッシュボード。リアルタイム機能を作ろうとすると、毎回同じことを繰り返す。

- WebSocketサーバーを立てる
- 接続管理、再接続ロジックを書く
- Redis Pub/Subでメッセージブローカーを構築
- クライアント側の状態管理と同期処理
- スケールアウト時のセッション管理

ただデータを同期したいだけなのに、インフラ周りで時間を取られる。

Convexを試してみたら、この部分がごっそり不要になった。

## Convexの仕組み

Convexはリアクティブなバックエンドプラットフォームで、データベース、サーバー関数、リアルタイム同期が一体化している。

特徴を3つ挙げる。

**1. TypeScriptだけで書ける**

SQLもORMも使わない。データベースのクエリもミューテーションも、TypeScriptで書く。

**2. 自動でリアルタイム同期される**

クライアントがクエリを購読すると、データが変わるたびに自動で再実行されて結果がプッシュされる。WebSocketの実装は書かない。

**3. ACIDトランザクションが保証される**

楽観的並行制御とシリアライザブル分離レベルを採用している。データの不整合が起きない。

では、実際のコードを見ていく。

## 実装例：リアルタイムメッセージリスト

### 1. スキーマ定義

```typescript
// convex/schema.ts
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  messages: defineTable({
    author: v.string(),
    body: v.string(),
    createdAt: v.number(),
  }).index("by_created", ["createdAt"]),
});
```

### 2. クエリ関数

```typescript
// convex/messages.ts
import { query } from "./_generated/server";

export const list = query(async ({ db }) => {
  return await db
    .query("messages")
    .withIndex("by_created")
    .order("desc")
    .take(50);
});
```

これでリアルタイムクエリが動く。SQLは書いていない。

### 3. ミューテーション関数

```typescript
// convex/messages.ts
import { mutation } from "./_generated/server";
import { v } from "convex/values";

export const send = mutation({
  args: { author: v.string(), body: v.string() },
  handler: async ({ db }, { author, body }) => {
    await db.insert("messages", {
      author,
      body,
      createdAt: Date.now(),
    });
  },
});
```

### 4. Reactコンポーネント

```typescript
// app/Chat.tsx
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";

export function Chat() {
  const messages = useQuery(api.messages.list);
  const sendMessage = useMutation(api.messages.send);

  if (messages === undefined) return <div>Loading...</div>;

  return (
    <div>
      {messages.map((msg) => (
        <div key={msg._id}>
          <strong>{msg.author}:</strong> {msg.body}
        </div>
      ))}
      <button onClick={() => sendMessage({ author: "me", body: "Hello!" })}>
        Send
      </button>
    </div>
  );
}
```

`useQuery`で購読すると、他のユーザーがメッセージを送信した瞬間に画面が更新される。WebSocketの接続管理もRedisも書いていない。

## 裏側で何が起きているか

```
[ブラウザ] ←WebSocket→ [Convex Cloud]
    ↓                      ↓
 useQuery()          クエリ実行
    ↓                      ↓
 購読登録           依存関係を追跡
    ↓                      ↓
（待機中）          データ変更検知
    ↓                      ↓
 自動更新 ←────── 差分プッシュ
```

流れはこうなっている。

1. クライアントが`useQuery`を呼ぶとWebSocket経由で購読が始まる
2. Convexがクエリを実行し、どのテーブル・行に依存しているか追跡する
3. ミューテーションでデータが変わると、影響を受けるクエリを特定する
4. 該当クエリを再実行し、購読中のクライアントにプッシュする

依存関係の追跡が自動なので、どのクエリがどのデータに依存しているか自分で管理する必要がない。ここが一番ありがたい。

## 従来手法との比較

| 項目 | ポーリング | WebSocket自前 | Convex |
|------|-----------|--------------|--------|
| データ鮮度 | リクエスト間隔に依存 | リアルタイム | リアルタイム |
| サーバー実装 | REST API | WebSocket + Pub/Sub | TypeScript関数のみ |
| クライアント実装 | fetch + setInterval | socket.io + 状態管理 | useQuery() |
| スケーリング | 容易 | Redis等が必要 | マネージド |
| 型安全性 | 手動で型定義 | 手動で型定義 | 自動生成 |

WebSocket自前で組むと、スケーリング時にRedisやセッション管理が必要になる。Convexはそこがマネージドなので、アプリのロジックに集中できる。

## 認証との連携

Convex Authを使えば、認証済みユーザーだけがアクセスできるクエリも書ける。

```typescript
// convex/messages.ts
import { query } from "./_generated/server";
import { getAuthUserId } from "@convex-dev/auth/server";

export const myMessages = query(async (ctx) => {
  const userId = await getAuthUserId(ctx);
  if (!userId) throw new Error("Unauthorized");

  return await ctx.db
    .query("messages")
    .withIndex("by_author", (q) => q.eq("author", userId))
    .collect();
});
```

## 料金体系

無料枠が結構使える。

- 月間100万関数呼び出し
- 1GBストレージ
- 1GB帯域幅

個人開発やプロトタイプなら無料枠で十分。本番運用もスタートアップ向けの価格設定になっている。

## 向いているケース、向いていないケース

Convexが向いているケース:

- **リアルタイムコラボレーション**: ドキュメント共同編集、ホワイトボード
- **チャット・メッセージング**: 1対1、グループチャット
- **ライブダッシュボード**: 分析画面、モニタリング
- **ゲーム**: ターンベースゲーム、マルチプレイヤーの状態同期
- **通知システム**: プッシュ通知、アクティビティフィード

一方、向いていないケースもある。

- 低レイテンシが極めて重要なリアルタイムゲーム（FPSなど）
- 既存のRDBMSに強く依存したシステムの移行
- SQLを直接書きたい場合

## はじめ方

```bash
npm create convex@latest
```

これでプロジェクトが立ち上がる。React、Next.js、Vue、Svelteのテンプレートが用意されている。

```bash
npx convex dev
```

開発サーバーを起動すると、`convex/`フォルダ内の変更が自動でデプロイされる。ホットリロードでバックエンドを開発できる。

## 使ってみた感想

リアルタイム同期を自分で実装すると、WebSocketの接続管理、Pub/Sub、状態同期と、本来作りたい機能以外のコードが増えていく。Convexはその部分を丸ごと引き受けてくれる。

TypeScriptで型安全に書けて、ACIDトランザクションも保証される。個人開発でリアルタイム機能を入れたいときの選択肢として、試してみる価値はある。

## 参考リンク

- [Convex公式サイト](https://www.convex.dev/)
- [Convex Documentation](https://docs.convex.dev/)
- [Convex Stack - Real-time Database Guide](https://stack.convex.dev/real-time-database)
- [GitHub - convex-backend](https://github.com/get-convex/convex-backend)
