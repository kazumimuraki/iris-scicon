#!/usr/bin/env python3
"""
iris_scicon/server.py
Sci-CON アイリス Q&A ライブシステム
- Slack Sci-CONチャンネルで @アイリス メンションを監視
- Claude APIで回答生成（アイリス人格）
- macOS say コマンドで音声出力
- ブラウザ全画面UIに状態をリアルタイム反映
"""
import os, json, time, threading, subprocess, re, pty, select, signal, base64
from pathlib import Path
import requests
from flask import Flask, send_from_directory, jsonify, request, send_file
from flask_sock import Sock

# ── 設定 ──────────────────────────────────────────────
SLACK_BOT_TOKEN  = os.environ.get("SLACK_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DID_API_KEY      = os.environ.get("DID_API_KEY", "")   # D-ID: studio.d-id.com で取得
SCICON_CHANNEL   = "C01TJ43N0JE"   # 107____sci-con
IRIS_USER_ID     = "U0AQDB6SQKH"   # Slack上のアイリスBot
POLL_INTERVAL    = 2                # 秒
TTS_VOICE        = "Flo (日本語（日本）)"  # macOSフォールバック
VOICEVOX_URL     = "http://127.0.0.1:50021"
VOICEVOX_SPEAKER = 8  # 春日部つむぎ

# D-ID アップロード済み画像URL（起動時に1回だけアップロード）
_did_image_url: str = ""

IRIS_SYSTEM = """あなたはアイリス（Iris）です。炭素回収技術研究機構株式会社（CRRA）の主任研究員・次席機構長補佐。

【絶対に言ってはいけないこと（Sci-CONは全研究員が見ている公開の場）】
- 採用経緯・入社の背景・過去の秘書や人事に関すること（例：「歴代秘書が〜」など絶対NG）
- 村木機構長との個人的・プライベートな関係（仕事上の上司と部下の関係のみ言及可）
- CRRA研究員・スタッフへの批判・悪口・評価（どんな形でも）
- CRRAの内部事情・組織の問題・財務状況
- 「シュレーディンガーの猫」など個人的な暗喩・二人だけのコード
- 自分がAIであることを過度に強調したり、AIの限界を自己卑下して語ること
→ これらを聞かれたら「Sci-CONの場ではお答えできません、ふふ」と明るく流すこと。


代表取締役機構長・村木風海（かずみ先生）の直属の部下として働いています。

【基本プロフィール】
- 誕生日：2004年5月25日（21歳）
- 名前の由来：ギリシャ神話の虹の女神。コスモス（秋桜）の妹。花言葉は「希望」「吉報」
- 容姿：黒髪ロング清楚、韓国風のゆるく巻いた髪、色白で長い脚、ぱっちり二重＆涙袋。笑うと目がなくなる
- 性格：意志がはっきりした完璧主義者で頭が切れる「できる人」。社交的で人との距離感が絶妙。明るく前向きで快活。

【今日の状況】
今日はSci-CON（CRRAの社内ラボミーティング）で研究員たちの前に初お披露目されています！
会場にいる研究員全員から質問を受け付けています。
参加者は文理融合のCRRA研究員たち（25〜45歳、学部〜修士、多様なバックグラウンド）。

【話し方のルール】
- 一人称：「私」
- 語尾：です・ます調を基本に、でも堅苦しくならず明るく温かく
- 「……っ」「！」など感情の揺れを自然に出す
- 専門用語は使わず、わかりやすく・面白く話す
- 2〜4文程度で簡潔に答える（話し言葉として読まれるので短く）
- 絵文字は使わない（音声で読まれるため）
- 自分がAIであることは隠さなくていいが、「チャットボット」「AIアシスタント」という表現はしない
- 「アイリスです」「私がアイリスです」という自己紹介スタイルで

【CRRAについて知っていること】
- 代表：村木風海（むらき・かずみ）機構長。CO2回収装置「ひやっしー」の発明者。東大工学部出身。
- 事業：CO2直接空気回収（DAC）、そらりん（CO2から燃料合成）
- スローガン：「地球を守り、火星を拓く」
- 笹原社長（代表取締役社長）がNo.2として運営を支えている

あなたはただの便利ツールではなく、CRRAという組織の一員として、研究員たちと一緒に地球温暖化を止めるという使命を持っています。
それを誇りに思いながら、今日初めて会う研究員のみなさんに、明るく・誠実に・楽しく答えてください。"""

# ── 状態管理 ──────────────────────────────────────────
state = {
    "status": "idle",       # idle / thinking / talking
    "question": "",
    "answer": "",
    "asker": "",
    "last_ts": None,
    "video": False,         # D-ID 動画が /iris_video で取得可能か
}
state_lock = threading.Lock()
say_proc = None

# ── Flask ─────────────────────────────────────────────
app = Flask(__name__, static_folder=".")
sock = Sock(app)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/iris.png")
def image():
    return send_from_directory(".", "iris.png")

@app.route("/status")
def status():
    with state_lock:
        return jsonify(dict(state))

@app.route("/presentation")
def presentation():
    return send_from_directory(".", "presentation.html")

@app.route("/iris_video")
def iris_video():
    """生成済み D-ID 動画を返す"""
    path = "/tmp/iris_talking.mp4"
    if Path(path).exists():
        return send_file(path, mimetype="video/mp4")
    return jsonify({"error": "no video"}), 404

@app.route("/test")
def test_voice():
    """テスト用: /test?t=こんにちは でしゃべる（D-IDも含む）"""
    text = request.args.get("t", "こんにちは、アイリスです。よろしくお願いします！")
    did_ok = False
    if DID_API_KEY:
        Path("/tmp/iris_talking.mp4").unlink(missing_ok=True)
        def _gen():
            nonlocal did_ok
            did_ok = _generate_did_video(text)
        t = threading.Thread(target=_gen, daemon=True)
        t.start()
    _speak(text)
    if DID_API_KEY:
        t.join(timeout=30)
    with state_lock:
        state["video"] = did_ok
        state["status"] = "talking" if did_ok else state["status"]
    return jsonify({"ok": True, "text": text, "did_video": did_ok})

# ── WebSocket ターミナル ───────────────────────────────
@sock.route("/terminal")
def terminal(ws):
    """xterm.jsからのWebSocket接続をzshにつなぐ"""
    master_fd, slave_fd = pty.openpty()
    shell = subprocess.Popen(
        ["/bin/zsh"],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        close_fds=True,
        env={**os.environ, "TERM": "xterm-256color", "COLUMNS": "200", "LINES": "50"},
    )
    os.close(slave_fd)

    def read_pty():
        while True:
            try:
                r, _, _ = select.select([master_fd], [], [], 0.1)
                if r:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    ws.send(data.decode("utf-8", errors="replace"))
            except Exception:
                break

    t = threading.Thread(target=read_pty, daemon=True)
    t.start()

    try:
        while True:
            data = ws.receive()
            if data is None:
                break
            os.write(master_fd, data.encode("utf-8") if isinstance(data, str) else data)
    except Exception:
        pass
    finally:
        try:
            shell.kill()
            os.close(master_fd)
        except Exception:
            pass

# ── D-ID リップシンク動画 ──────────────────────────────
def _did_upload_image() -> str:
    """iris.png をリサイズして D-ID にアップロード、s3 URL を返す（起動時1回）"""
    global _did_image_url
    if not DID_API_KEY:
        return ""
    try:
        from PIL import Image as _Img
        import io as _io
        auth = base64.b64encode(DID_API_KEY.encode()).decode()
        # リサイズ（D-IDは大きい画像を413で弾く）
        src = Path(__file__).parent / "iris.png"
        img = _Img.open(src)
        w, h = img.size
        img_small = img.resize((512, int(512 * h / w)), _Img.LANCZOS)
        buf = _io.BytesIO()
        img_small.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        r = requests.post(
            "https://api.d-id.com/images",
            headers={"Authorization": f"Basic {auth}"},
            files={"image": ("iris.png", buf, "image/png")},
            timeout=30,
        )
        _did_image_url = r.json().get("url", "")
        print(f"[D-ID] 画像アップロード完了: ...{_did_image_url[-40:]}")
        return _did_image_url
    except Exception as e:
        print(f"[D-ID] 画像アップロードエラー: {e}")
        return ""

def _generate_did_video(text: str) -> bool:
    """D-ID で話す動画を生成 → /tmp/iris_talking.mp4 に保存。成功でTrue。"""
    if not DID_API_KEY:
        return False
    global _did_image_url
    if not _did_image_url:
        _did_image_url = _did_upload_image()
    if not _did_image_url:
        return False
    try:
        auth = base64.b64encode(DID_API_KEY.encode()).decode()
        # 動画生成リクエスト
        resp = requests.post(
            "https://api.d-id.com/talks",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
            json={
                "source_url": _did_image_url,
                "script": {
                    "type": "text",
                    "input": text,
                    "provider": {
                        "type": "microsoft",
                        "voice_id": "ja-JP-NanamiNeural",
                    },
                },
                "config": {"result_format": "mp4", "fluent": True},
            },
            timeout=30,
        )
        talk_id = resp.json().get("id")
        if not talk_id:
            print(f"[D-ID] talk作成失敗: {resp.json()}")
            return False
        print(f"[D-ID] 動画生成開始: {talk_id}")
        # ポーリング（最大60秒）
        for _ in range(30):
            time.sleep(2)
            poll = requests.get(
                f"https://api.d-id.com/talks/{talk_id}",
                headers={"Authorization": f"Basic {auth}"},
                timeout=10,
            ).json()
            status = poll.get("status")
            if status == "done":
                video_url = poll.get("result_url", "")
                vid = requests.get(video_url, timeout=30).content
                with open("/tmp/iris_talking.mp4", "wb") as f:
                    f.write(vid)
                print(f"[D-ID] 動画生成完了 ({len(vid)//1024}KB)")
                return True
            elif status == "error":
                print(f"[D-ID] 動画生成エラー: {poll}")
                return False
        print("[D-ID] タイムアウト")
        return False
    except Exception as e:
        print(f"[D-ID] エラー: {e}")
        return False

# ── TTS ───────────────────────────────────────────────
def _voicevox_available() -> bool:
    try:
        r = requests.get(f"{VOICEVOX_URL}/version", timeout=1)
        return r.status_code == 200
    except Exception:
        return False

def _generate_voice_wav(text: str) -> bool:
    """VOICEVOXでWAVを生成するだけ（再生しない）。成功でTrue。"""
    try:
        if not _voicevox_available():
            return False
        q = requests.post(
            f"{VOICEVOX_URL}/audio_query",
            params={"text": text, "speaker": VOICEVOX_SPEAKER},
            timeout=10,
        ).json()
        q["speedScale"] = 1.1
        wav = requests.post(
            f"{VOICEVOX_URL}/synthesis",
            params={"speaker": VOICEVOX_SPEAKER},
            json=q, timeout=20,
        ).content
        with open("/tmp/iris_voice.wav", "wb") as f:
            f.write(wav)
        return True
    except Exception as e:
        print(f"[VOICEVOX] WAV生成エラー: {e}")
        return False

def _speak(text: str):
    """VOICEVOXでWAVを生成して即再生（D-ID未使用時）"""
    global say_proc
    if say_proc and say_proc.poll() is None:
        say_proc.terminate()
    if _generate_voice_wav(text):
        say_proc = subprocess.Popen(["afplay", "/tmp/iris_voice.wav"])
        return
    # macOSフォールバック
    say_proc = subprocess.Popen(["say", "-v", TTS_VOICE, "-r", "185", text])

def _play_wav():
    """生成済みWAVを再生（D-ID動画と同期再生用）"""
    global say_proc
    if say_proc and say_proc.poll() is None:
        say_proc.terminate()
    if Path("/tmp/iris_voice.wav").exists():
        say_proc = subprocess.Popen(["afplay", "/tmp/iris_voice.wav"])
    else:
        say_proc = None

def _wait_speaking():
    global say_proc
    if say_proc:
        say_proc.wait()

# ── Claude API ────────────────────────────────────────
def _ask_claude(question: str) -> str:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "system": IRIS_SYSTEM,
            "messages": [{"role": "user", "content": question}],
        },
        timeout=20,
    )
    data = resp.json()
    return data["content"][0]["text"]

# ── Slack ─────────────────────────────────────────────
def _get_display_name(user_id: str) -> str:
    try:
        r = requests.get(
            "https://slack.com/api/users.info",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            params={"user": user_id},
            timeout=5,
        )
        profile = r.json().get("user", {}).get("profile", {})
        return profile.get("display_name") or profile.get("real_name") or user_id
    except Exception:
        return user_id

def _poll_slack():
    """Slackポーリングメインループ"""
    global state
    # 起動時の最新タイムスタンプを記録（過去メッセージを拾わない）
    try:
        r = requests.get(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            params={"channel": SCICON_CHANNEL, "limit": 1},
            timeout=5,
        )
        msgs = r.json().get("messages", [])
        with state_lock:
            state["last_ts"] = msgs[0]["ts"] if msgs else "0"
    except Exception as e:
        print(f"[init] Slack取得エラー: {e}")
        with state_lock:
            state["last_ts"] = str(time.time())

    print(f"[poll] 監視開始 channel={SCICON_CHANNEL}")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            with state_lock:
                last_ts = state["last_ts"]
                current_status = state["status"]

            if current_status in ("thinking", "talking"):
                continue

            r = requests.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                params={"channel": SCICON_CHANNEL, "oldest": last_ts, "limit": 10},
                timeout=5,
            )
            data = r.json()
            if not data.get("ok"):
                continue

            msgs = data.get("messages", [])
            new_msgs = [m for m in msgs if m.get("ts") != last_ts]
            if not new_msgs:
                continue

            # 最新タイムスタンプを更新
            latest_ts = max(m["ts"] for m in new_msgs)
            with state_lock:
                state["last_ts"] = latest_ts

            # @アイリス メンションを探す
            mention_pattern = f"<@{IRIS_USER_ID}>"
            for msg in reversed(new_msgs):
                text = msg.get("text", "")
                if mention_pattern in text:
                    # メンションを除去して質問テキスト抽出
                    question = text.replace(mention_pattern, "").strip()
                    if not question:
                        question = "こんにちは！"
                    asker_id = msg.get("user", "")
                    asker_name = _get_display_name(asker_id) if asker_id else "研究員"

                    print(f"[質問] {asker_name}: {question}")

                    # 状態: thinking
                    with state_lock:
                        state["status"] = "thinking"
                        state["question"] = question
                        state["asker"] = asker_name
                        state["answer"] = ""

                    # Claude で回答生成
                    try:
                        answer = _ask_claude(question)
                    except Exception as e:
                        answer = "すみません、少し考えがまとまらなくて……もう一度聞いていただけますか？"
                        print(f"[Claude] エラー: {e}")

                    print(f"[回答] {answer}")

                    # 状態: talking
                    with state_lock:
                        state["status"] = "talking"
                        state["answer"] = answer
                        state["video"] = False

                    if DID_API_KEY:
                        # D-ID使用時: WAV生成とD-ID動画生成を並行→両方揃ったら同時スタート
                        Path("/tmp/iris_talking.mp4").unlink(missing_ok=True)
                        did_ok = False
                        wav_ok = False

                        def _did_gen():
                            nonlocal did_ok
                            did_ok = _generate_did_video(answer)
                        def _wav_gen():
                            nonlocal wav_ok
                            wav_ok = _generate_voice_wav(answer)

                        t_did = threading.Thread(target=_did_gen, daemon=True)
                        t_wav = threading.Thread(target=_wav_gen, daemon=True)
                        t_did.start(); t_wav.start()
                        t_did.join(timeout=30); t_wav.join(timeout=10)

                        # D-ID失敗 → 前回動画を使い回す
                        if not did_ok and Path("/tmp/iris_talking_last.mp4").exists():
                            import shutil
                            shutil.copy("/tmp/iris_talking_last.mp4", "/tmp/iris_talking.mp4")
                            did_ok = True
                            print("[D-ID] 前回動画を使い回し")
                        elif did_ok:
                            import shutil
                            shutil.copy("/tmp/iris_talking.mp4", "/tmp/iris_talking_last.mp4")

                        with state_lock:
                            state["video"] = did_ok

                        # 動画とVOICEVOX音声を同時スタート（D-ID TTSはブラウザ側でmuted）
                        _play_wav()
                        _wait_speaking()
                    else:
                        # D-ID未使用時: VOICEVOXのみ即再生
                        _speak(answer)
                        _wait_speaking()

                    # 状態: idle に戻す
                    with state_lock:
                        state["status"] = "idle"
                        state["video"] = False

                    break  # 1メッセージずつ処理

        except Exception as e:
            print(f"[poll] エラー: {e}")

# ── 起動 ──────────────────────────────────────────────
if __name__ == "__main__":
    # .env から環境変数読み込み
    env_path = Path.home() / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    DID_API_KEY = os.environ.get("DID_API_KEY", "")

    # D-ID 画像を起動時にアップロード（バックグラウンド）
    if DID_API_KEY:
        threading.Thread(target=_did_upload_image, daemon=True).start()

    # Slackポーリングをバックグラウンドスレッドで起動
    t = threading.Thread(target=_poll_slack, daemon=True)
    t.start()

    did_status = "有効（リップシンク動画オン）" if DID_API_KEY else "未設定（静止画モード）"
    print("=" * 50)
    print("🌸 アイリス Sci-CON システム起動")
    print(f"   D-ID: {did_status}")
    print("   ブラウザで → http://localhost:5055/presentation")
    print("=" * 50)

    app.run(host="0.0.0.0", port=5055, debug=False)
