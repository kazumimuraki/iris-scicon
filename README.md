# iris-scicon

**CRRA Sci-CON 2026-04-24 — AI Avatar Presentation + Live Q&A System**

## 概要
炭素回収技術研究機構（CRRA）の内部研究発表会「Sci-CON」向けに開発した、  
AIアバター（アイリス）によるリアルタイムQ&Aシステム付きプレゼンテーション。

## 機能
- **reveal.js** — 13スライド・30分講義対応プレゼン（16:9固定）
- **VOICEVOX** — 春日部つむぎ（speaker=8）によるリアルタイムTTS
- **D-ID** — リップシンク動画生成（静止画+テキスト→動画）
- **Slack連携** — #sci-conへの@アイリス質問をリアルタイムで受付・回答
- **Claude API** — 回答生成バックエンド
- **埋め込みTerminal** — flask-sock + xterm.js（WebSocket）

## 起動方法
```bash
cd ~/iris_scicon && \
  SLACK_BOT_TOKEN=xxx \
  ANTHROPIC_API_KEY=xxx \
  DID_API_KEY=xxx \
  python3 -u server.py
```
→ http://localhost:5055/presentation

## 要素技術（次回流用ポイント）
| コンポーネント | ファイル | 備考 |
|---|---|---|
| D-ID APIリップシンク | server.py `_generate_did_video()` | 画像512px以下に要リサイズ |
| VOICEVOX TTS | server.py `_generate_voice_wav()` | port 50021, speaker=8 |
| Canvas/Video切替 | presentation.html JS | 静止画↔リップシンク動画 |
| Slack Q&Aポーリング | server.py `_poll_slack()` | Bot token + チャンネルID |
| reveal.js 16:9固定 | presentation.html | width:1920, height:1080 必須 |

## 反省・次回への教訓
→ 詳細は [Sci-CON反省メモ](.claude/feedback_scicon_presentation.md) 参照
