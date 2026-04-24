# Sci-CON 2026-04-24 プレゼン計画

## 今日の発表テーマ
1. AIの最新動向解説（AI勢力図2026）
2. Claude Codeの使い方
3. アイリスお披露目 & ライブQ&Aショー

## 持ち時間：30分
## 聴衆：CRRA研究員全員（文理融合・学部〜修士・主婦出身含む）

---

## 全体構成（30分）

| # | 時間 | 内容 | ツール |
|---|------|------|--------|
| 1 | 5分 | AI勢力図2026：GPT vs Gemini vs Claude | スライド |
| 2 | 3分 | Claude vs Claude Code、何が違う？ | スライド |
| 3 | 12分 | アイリスお披露目 & Slackライブ Q&A | iris_scicon システム |
| 4 | 10分 | ライブデモ（Claude Code実演） | ターミナル |

---

## パート1：AI勢力図2026（スライド）
- GPT-4o / GPT-o3：一般普及・マルチモーダル
- Gemini 2.5：Google統合・検索最強
- Claude 3.7 / Sonnet 4.6：コーディング・長文・推論最強
- 得意不得意マップ（チャート）
- 「みんなGPTかGeminiで止まってるけど、実はClaudeが一番すごい」

## パート2：Claude vs Claude Code（スライド）
- Claude（ブラウザ）= チャットで会話するAI
- Claude Code（ターミナル）= ファイル・コード・PCを直接操作するAI
- アイリスはClaude Codeで動いている

## パート3：アイリスお披露目（iris_sciconシステム）
- スクリーンにアイリスの写真＋名前カード
- 「実はこのアイリスが機構のAI主任研究員です」
- Slackの #107____sci-con で @アイリス にメンション → 全画面で回答＋音声

## パート4：ライブデモ（Claude Code実演）
- カレンダー作成・スケジュール調整
- メール返信文生成
- 余裕があれば：CRRAウェブサイト改善案を目の前でコーディング

---

## TODOチェックリスト

### 今すぐやること（13:00まで）
- [x] iris_scicon システム起動・動作確認
- [ ] スライド作成（reveal.js or Marp）→ パート1〜2分
- [ ] Sci-CONチャンネルにアイリスBotを招待（Slackで /invite @アイリス）
- [ ] テストメンション送って音声・画面確認
- [ ] 音声テスト：http://localhost:5055/test?t=こんにちは

### プレゼン中の操作手順
1. Chrome全画面で http://localhost:5055 を開く
2. スライドを別タブで開く
3. スライドパート終わったらiris_sciconタブに切り替え
4. 研究員にSlackでメンションしてもらう

---

## スライド作成メモ（Marp）

ファイル: ~/iris_scicon/slides.md
出力: marp slides.md --html --output slides.html

