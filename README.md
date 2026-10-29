# 影片內容分析工具

給一個短影音網址（Instagram Reel/貼文、TikTok、YouTube Shorts 等），抓出貼文的metadata
（文案、按讚數、留言數、觀看數、發文日期）和逐字稿（用本機 Whisper 模型語音轉文字，
不需要任何 API key）。之後把這份 JSON 丟給 Claude，就能分析這支影片為什麼會有流量、
並整理出內容大綱。

## 安裝

```bash
pip install -r requirements.txt
```

需要系統已安裝 `ffmpeg`。

## 使用

```bash
python3 scripts/analyze_video.py "<影片網址>"
```

常用參數：

- `--model`：Whisper 模型大小，`tiny/base/small/medium/large-v3`（預設 `medium`，模型越大越準但越慢）
- `--language`：強制指定語言，例如 `zh`、`en`（預設自動偵測）
- `--output result.json`：同時把結果存成檔案
- `--keep-media`：保留下載下來的音訊檔（預設用完即刪）
- `--cookies cookies.txt` / `--cookies-from-browser chrome`：私人帳號或需要登入才能看的貼文，需要提供 cookies

輸出是一個 JSON，包含：

```json
{
  "metadata": { "title": "...", "caption": "...", "like_count": 0, "view_count": 0, "upload_date": "..." },
  "transcript": { "full_text": "...", "segments": [{"start": 0.0, "end": 3.2, "text": "..."}] }
}
```

## 限制

- 這支工具只負責「抓資料 + 轉文字」，不會自己判斷「為什麼爆紅」或生大綱——那部分是
  把輸出的 JSON 丟給 Claude 後，由 Claude 直接分析。
- 需要能連到影片平台（instagram.com / tiktok.com / youtube.com 等）的網路權限。在部分
  雲端沙盒環境（例如預設的 Claude Code 雲端 session）這些網域可能被網路政策擋掉，需要
  到該環境設定的「Network access」把這些網域加進允許清單，或改用能完整上網的環境／
  自己的電腦執行。
- 私人帳號或登入才能看的貼文，需要提供 `--cookies`，否則 yt-dlp 會抓不到內容。
- 影片越長，用 CPU 跑 Whisper 轉錄越慢；`large-v3` 品質最好但也最慢，一般先用 `medium` 即可。
