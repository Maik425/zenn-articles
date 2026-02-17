#!/usr/bin/env python3
"""
Zenn記事公開時にXで告知するスクリプト

GitHub Actionから呼ばれ、published: false → true に変更された記事を検出し、
Xに告知ツイートを投稿する。
"""

import os
import re
import subprocess
import sys

import tweepy
import yaml


def get_newly_published_articles(before_sha):
    """published が false → true に変更された記事を検出"""

    # 初回push（before_shaが全ゼロ）はスキップ
    if before_sha == '0' * 40:
        print("初回pushのためスキップ")
        return []

    # 変更・追加されたファイル一覧
    result = subprocess.run(
        ['git', 'diff', '--name-only', '--diff-filter=AM',
         before_sha, 'HEAD', '--', 'articles/'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"git diff failed: {result.stderr}")
        return []

    changed_files = [
        f.strip() for f in result.stdout.strip().split('\n')
        if f.strip().endswith('.md')
    ]
    if not changed_files:
        print("変更された記事ファイルなし")
        return []

    published = []
    for filepath in changed_files:
        if not os.path.exists(filepath):
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue

        current_fm = yaml.safe_load(fm_match.group(1))
        if not current_fm.get('published'):
            continue

        # 以前のバージョンを確認
        old = subprocess.run(
            ['git', 'show', f'{before_sha}:{filepath}'],
            capture_output=True, text=True,
        )
        if old.returncode == 0:
            old_match = re.match(r'^---\n(.*?)\n---', old.stdout, re.DOTALL)
            if old_match:
                old_fm = yaml.safe_load(old_match.group(1))
                if old_fm.get('published'):
                    continue  # 既に公開済み

        slug = os.path.splitext(os.path.basename(filepath))[0]
        published.append({
            'title': current_fm.get('title', slug),
            'slug': slug,
        })

    return published


def post_to_x(title, url):
    """Xに告知ツイートを投稿"""
    client = tweepy.Client(
        consumer_key=os.environ['X_CONSUMER_KEY'],
        consumer_secret=os.environ['X_CONSUMER_SECRET'],
        access_token=os.environ['X_ACCESS_TOKEN'],
        access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET'],
    )

    # 本文を構築（URLは別カウント、本文は100文字以内を目標）
    prefix = "Zennに記事を公開しました\n\n"
    max_title = 100 - len(prefix)
    if len(title) > max_title:
        title = title[:max_title - 1] + "…"
    body = f"{prefix}{title}"
    tweet = f"{body}\n\n{url}"

    result = client.create_tweet(text=tweet)
    tweet_id = result.data['id']
    print(f"  posted: https://x.com/i/status/{tweet_id}")
    return tweet_id


def main():
    before_sha = os.environ.get('BEFORE_SHA', '')
    zenn_username = os.environ.get('ZENN_USERNAME', '')

    if not before_sha:
        print("ERROR: BEFORE_SHA not set")
        sys.exit(1)
    if not zenn_username:
        print("ERROR: ZENN_USERNAME not set")
        sys.exit(1)

    articles = get_newly_published_articles(before_sha)
    if not articles:
        print("新しく公開された記事なし")
        return

    print(f"{len(articles)}件の記事が公開されました")
    for article in articles:
        url = f"https://zenn.dev/{zenn_username}/articles/{article['slug']}"
        print(f"  {article['title']}")
        print(f"  {url}")
        try:
            post_to_x(article['title'], url)
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == '__main__':
    main()
