---
name: junior-engineer-screening-playwright
model: claude-haiku-4-5-20251001
description: |
  ローカルPlaywright MCPを使って、リクルートマーカー（app.recruit-marker.jp）で若手エンジニア候補者を
  スクリーニングするスキル。リクルートマーカーへのログインとYouTrustへのログインを自動検出し、
  未ログインの場合はセッション保存つきのログインフローをガイドする。
  各候補者のLinkedIn/YouTrustプロフィールを確認し、採用要件（日本国籍・Webエンジニア経験2-3年以上・
  フルスタック経験）に合致しない候補者を理由付きでリストアップし、MDレポートとして出力する。
  「若手エンジニアのスクリーニング」「候補者をチェックして」「リストのスクリーニングをして」
  「採用候補者をフィルタリング」「リクマのリストを確認」「候補者を絞り込んで」
  「スクリーニングして」「リクルートマーカーで確認」「採用リストのチェック」
  「エンジニア候補の選別」「若手エンジニアリストを確認」
  といったリクエストで必ずこのスキルを使うこと。
---

# 若手エンジニア候補者スクリーニング（Playwright版）

リクルートマーカー（https://app.recruit-marker.jp/）上の候補者リストに対して、
LinkedIn / YouTrust のプロフィール情報をもとに採用要件チェックを行い、
要件に合致しない候補者を理由付きでリストアップするスキル。

**使用ツール:** ローカルPlaywright MCP（`mcp__plugin_playwright_playwright__*`）

## Playwright MCPツール早見表

| 操作 | 使用ツール |
|------|-----------|
| ページ移動 | `browser_navigate` |
| ページ内容取得（YouTrust等） | `browser_snapshot`（アクセシビリティツリー）|
| ページ内容取得（LinkedIn） | `browser_evaluate` で `document.querySelector('main').innerText.substring(0, 5000)` |
| JavaScript実行 | `browser_evaluate` |
| スクロール | `browser_evaluate` で `window.scrollBy(0, N)` または `browser_press_key` で "PageDown" |
| クリック | `browser_click` |
| 入力 | `browser_fill` または `browser_type` |
| スクリーンショット | `browser_take_screenshot` |
| 待機 | `browser_wait_for` |
| タブ一覧 | `browser_tabs` |
| キー入力 | `browser_press_key` |

---

## ワークフロー概要

```
1. リクルートマーカーにアクセス → ログイン確認・必要ならログインガイド
2. YouTrustのログイン確認（事前チェック）
3. 作業リストの特定（URLまたはリスト名）
4. リストのグリッドからLinkedIn/YouTrustリンク＋テキスト情報を収集 → candidates_raw.json保存
5. バッチ処理（10名ずつ）：プロフィール巡回 → 中間保存 → サブエージェント判定 → 判定結果保存
6. 全バッチ完了後、結果をマークダウンファイルに出力
7. チャットで完了報告
```

## 重要: コンテキスト節約とレジリエンス設計

70名超の候補者を処理する場合、1人ずつのプロフィール巡回でコンテキストが溢れる。
以下の原則を必ず守ること：

1. **中間ファイル保存を必ず行う** — プロフィール情報は都度ファイルに保存し、メモリに頼らない
2. **バッチ処理（10名単位）** — 10名分のプロフィール収集 → ファイル保存 → サブエージェント判定 → 次のバッチ
3. **LinkedInは `browser_evaluate` でテキスト一括取得** — `browser_snapshot` は使わない（後述）
4. **進捗ファイルで再開可能に** — コンテキストリセット時も前回の続きから再開できる

---

## Step 1: リクルートマーカーへのアクセスとログイン処理

### 1-1: ページにアクセス

```
browser_navigate: https://app.recruit-marker.jp/
```

### 1-2: ログイン状態の確認

`browser_snapshot` でページ内容を取得し、以下で判定する：
- URLが `app.recruit-marker.jp/list` または `app.recruit-marker.jp/dashboard` 系 → **ログイン済み**
- URLが `app.recruit-marker.jp/login` や `auth` 系にリダイレクトされた → **未ログイン**

### 1-3: 未ログインの場合のログインフロー

ユーザーにログインを促す前に、まずPlaywrightブラウザでログインページを表示する。

```
browser_take_screenshot  # 現在の状態をユーザーに見せる
```

ユーザーへメッセージ:
> リクルートマーカーへのログインが必要です。Playwrightブラウザ（通常は別ウィンドウで表示中）で
> ログインをお願いします。ログインが完了したらお知らせください。

ログイン完了の報告を受けたら：
1. `browser_snapshot` でページ内容を再確認
2. セッション情報を保存する（後述の「セッション保存」参照）
3. 作業リストへ移動

### 1-4: セッション情報の保存

ログイン成功後、セッションを可能な限り保存する。
以下のJavaScriptでlocalStorageとsessionStorageの内容を抽出・保存する：

```javascript
// browser_evaluate で実行
const sessionData = {
  localStorage: Object.fromEntries(
    Object.keys(localStorage).map(k => [k, localStorage.getItem(k)])
  ),
  sessionStorage: Object.fromEntries(
    Object.keys(sessionStorage).map(k => [k, sessionStorage.getItem(k)])
  ),
  timestamp: new Date().toISOString(),
  url: location.href
};
JSON.stringify(sessionData);
```

取得したデータをファイルに保存:
- 保存先: `/Users/mor/co-work/採用/.session_cache/recruit-marker-session.json`

**注意:** HttpOnly Cookieはブラウザのセキュリティ制約によりJS経由では取得できない。
Playwright MCPのブラウザコンテキストはサーバーが起動している間はセッションを維持するため、
Playwright MCPを再起動しなければ通常は再ログイン不要。

---

## Step 2: YouTrustのログイン確認（事前チェック）

候補者のプロフィール確認前に、YouTrustのログイン状態を事前チェックする。

```
browser_navigate: https://youtrust.jp/
```

`browser_snapshot` でページ確認:
- ログインユーザー情報が表示されている → **ログイン済み**、リクルートマーカーに戻る
- ログインページが表示されている → **未ログイン**、ユーザーにガイド

### YouTrustが未ログインの場合

```
browser_take_screenshot  # 現状表示
```

ユーザーへメッセージ:
> YouTrustへのログインが必要です。Playwrightブラウザでログインしてください。
> （メール/パスワード or Googleログイン）
> ログイン完了後にお知らせください。

ログイン完了確認後、セッション保存:
- 保存先: `/Users/mor/co-work/採用/.session_cache/youtrust-session.json`

ログイン後はリクルートマーカーの対象リストURLへ戻る。

---

## Step 3: 作業リストの特定

ユーザーがリストURLを指定していれば直接アクセス：
```
browser_navigate: https://app.recruit-marker.jp/list/person-list/XXXXX
```

指定がない場合はユーザーに「どのリストで作業しますか？URLかリスト名を教えてください」と確認する。

---

## Step 4: リストからリンク情報の収集

### UIの特性

リスト画面はグリッド（テーブル）形式で候補者が表示される。
**重要: このリストは仮想化（virtualized）されており、スクロール位置によって表示行が変わる。**
スクロールしながら段階的にデータを収集する必要がある。

表示件数を100件に設定してから収集を開始する。

### 収集手順（JavaScript一括収集方式）

**Step A: 初期化**
```javascript
// browser_evaluate で実行
window.__allCandidates = {};
"initialized";
```

**Step B: 現在表示中の候補者データを収集（スクロールのたびに実行）**
```javascript
// browser_evaluate で実行
const links = [...document.querySelectorAll('a[href]')];
links.forEach(link => {
  const href = link.href;
  let type = null;
  if (href.includes('linkedin.com/in/')) type = 'linkedin';
  else if (href.includes('youtrust.jp/users/')) type = 'youtrust';
  else return;

  let row = link.parentElement;
  for (let i = 0; i < 20 && row; i++) {
    if (row.getAttribute && row.getAttribute('role') === 'row') break;
    if (row.children && row.children.length > 5) break;
    row = row.parentElement;
  }
  const rowText = row ? row.innerText : '';
  const lines = rowText.split('\n').filter(l => l.trim());

  const slug = type === 'linkedin'
    ? href.split('/in/')[1]?.split('/')[0]?.split('?')[0]
    : href.split('/users/')[1]?.split('/')[0]?.split('?')[0];
  if (!slug) return;

  if (!window.__allCandidates[slug]) {
    window.__allCandidates[slug] = { lines: lines.slice(0, 4) };
  }
  window.__allCandidates[slug][type] = href;
});
Object.keys(window.__allCandidates).length;
```

**Step C: スクロール（Playwright版）**
```javascript
// browser_evaluate で実行（約300px下へスクロール）
const grid = document.querySelector('[role="grid"]') || document.querySelector('[class*="list"]') || document.body;
grid.scrollBy(0, 300);
// または window.scrollBy(0, 300);
"scrolled";
```

もしくは `browser_press_key` で `PageDown` を使う。

**Step D: Step B → Step C を繰り返す**
収集数が総件数と一致するまで繰り返す（目安: リストの行数分）。

**Step E: 全データ取得**
```javascript
// browser_evaluate で実行
JSON.stringify(window.__allCandidates);
```

収集した `lines` 配列には会社名・タイトル・ヘッドラインが含まれ、Step 5の判定で活用する。

**Step F: candidates_raw.json に保存**

全データを取得した後、Writeツールで `/Users/mor/co-work/採用/candidates_raw.json` に保存する。
この JSON は以降のバッチ処理の入力として使い、コンテキストリセット時の再開にも利用する。

---

## Step 5: 候補者のプロフィール確認とスキル抽出（バッチ処理）

**【最重要ルール】全候補者のLinkedInまたはYouTrustプロフィールを必ず1人ずつ確認すること。**
リスト上の情報だけで判定禁止。プロフィールを開かずに「判定保留」にするのも禁止。

### バッチ処理の流れ

候補者が多い場合（20名超）、コンテキスト溢れを防ぐために **10名単位のバッチ** で処理する。

```
candidates_raw.json から10名ずつ取得
  ↓
各候補者のプロフィールを巡回（LinkedIn/YouTrust）
  ↓
プロフィール情報を candidates_profiles.json に追記保存
  ↓
10名分まとめて Opus サブエージェントで判定（Step 6）
  ↓
判定結果を screening_judgments.json に追記保存
  ↓
screening_progress.json の進捗を更新
  ↓
次の10名バッチへ
```

### 進捗管理ファイル

**`screening_progress.json`** — コンテキストリセット時に続きから再開するため

```json
{
  "list_url": "https://app.recruit-marker.jp/list/person-list/XXXXX",
  "list_name": "リスト名",
  "total_candidates": 70,
  "processed_slugs": ["slug1", "slug2"],
  "current_batch": 3,
  "last_updated": "2026-04-16T10:30:00Z"
}
```

### プロフィールの開き方

`browser_navigate` でURLに直接アクセスする。
リクルートマーカーに戻る必要はない（バッチ内で連続してプロフィールを巡回すればよい）。

### プロフィール情報源の優先順位

**YouTrustを最優先で確認する。** LinkedInより情報が豊富：
- スキルタグ（"Go", "React" 等が明確にリストされる）
- 自己紹介テキストのSkills一覧
- 職歴の会社名・役職・使用技術

**LinkedInも必ず確認する：**
- 3次つながりでもAbout・Skills・Experienceが表示されるケースが多い

### プロフィールの読み取り手順

**YouTrustの場合：**
1. `browser_navigate` でプロフィールURLにアクセス
2. `browser_snapshot` でページ全体のテキストを取得
3. スキルタグ・自己紹介文・職歴から技術キーワードを抽出

**LinkedInの場合（重要: browser_snapshotは使わない）：**

LinkedInのログイン済みページでは `browser_snapshot` や CSSセレクタ（`h1`, `.text-body-medium`, `#about`, `#experience`）で要素を取得しても空/nullが返る。
**唯一確実に動作する方法:**

1. `browser_navigate` でプロフィールURLにアクセス
2. ページ読み込みを2秒待機
3. 以下のJavaScriptで全テキストを一括取得:
   ```javascript
   // browser_evaluate で実行
   document.querySelector('main').innerText.substring(0, 5000)
   ```
4. 取得テキストからAbout・Experience・Skills情報を抽出

**注意:** `browser_snapshot` でLinkedInプロフィールを読もうとすると、アクセシビリティツリーに
主要セクションが含まれず空の結果になる。必ず `browser_evaluate` を使うこと。

### プロフィール取得後の中間保存

各バッチ（10名分）のプロフィール情報を取得したら、即座にファイルに保存する:

```json
// candidates_profiles.json に追記
{
  "slug": "john-doe",
  "name": "John Doe",
  "linkedin_url": "https://...",
  "youtrust_url": "https://...",
  "profile_text": "取得した全テキスト",
  "extracted_skills": ["React", "Go", "AWS"],
  "batch": 1
}
```

これにより、コンテキストが溢れても既に取得済みのプロフィール情報は失われない。

### 過去の判定ミス事例（必ず参照すること）

**ミス1: 会社名だけで不合格にした**
- 教訓: SIer企業（NRI等）でもプロフィールにWeb技術記載があればOK

**ミス2: タイトルだけで判断した**
- 教訓: 「SE」「システムエンジニア」でも実態はWebフルスタック開発のケースがある

**ミス3: 3次つながりで「詳細非表示」と早合点した**
- 教訓: スクロールすれば Vue/React + Go の記載が見えることが多い

**ミス4: ヘッドラインの「Backend」だけで判断した**
- 教訓: About欄でキャリア変遷を確認すること（フロント経験が過去にある場合がある）

**ミス5: プロフィールを開かずリスト情報だけで判断した**
- 教訓: LinkedInプロフィールに「Full-stack web developer」と明記されていることがある

### 抽出すべき技術キーワード

**バックエンド:** Ruby, Rails, Python, Django, Flask, FastAPI, Go, Golang, Java, Spring, Kotlin, PHP, Laravel, Node.js, Express, NestJS, Rust, C#, .NET, Elixir, Scala

**フロントエンド:** React, Vue.js, Angular, Next.js, Nuxt.js, Svelte, TypeScript, JavaScript, HTML, CSS, SCSS, Tailwind

**モバイル（フロントエンドとは別扱い）:** Swift, iOS, Android, React Native, Flutter, Dart

**インフラ/DevOps:** AWS, GCP, Azure, Docker, Kubernetes, Terraform, GitHub Actions, CircleCI

**DB:** MySQL, PostgreSQL, MongoDB, Redis, DynamoDB, Elasticsearch

### レート制限への配慮

- プロフィール間で `browser_wait_for` を使って2〜3秒待機する
- LinkedInのCAPTCHAが出た場合はユーザーに報告してYouTrustに切り替え
- 10件ごとに少し間を空ける

---

## Step 6: チェック要件による判定（Opusサブエージェントにバッチ委託）

**10名分のプロフィール情報が揃うたびに、Opusサブエージェントに判定を委託する。**
全候補者を一度に判定しようとするとコンテキストが溢れるため、必ずバッチ単位で実行する。

### Opusサブエージェントへの委託方法

各バッチ（10名分）のプロフィール収集完了後、以下の形式でサブエージェントを呼び出す：

```
Agentツールを使用:
  model: claude-opus-4-6
  prompt: |
    以下の候補者10名を採用要件に基づいて判定してください。

    ## 採用要件
    - 要件1: 日本国籍であること
    - 要件2: Webエンジニアとして2〜3年以上の経験
    - 要件3: フルスタック経験（サーバーサイド + フロントエンド）

    ## 候補者情報（バッチ N/M）
    [当該バッチ10名分のプロフィール情報を貼り付け]

    ## 判定基準の詳細
    [下記「判定基準」セクションの内容を全文貼り付け]

    ## 出力形式
    各候補者について以下のJSON配列で返してください:
    [{ "name": "名前", "slug": "linkedin-slug", "judgment": "合格/不合格/保留",
       "reason": "判定理由", "skills": ["React", "Go"] }]
```

### 判定結果の保存

サブエージェントの返答を `screening_judgments.json` に追記保存する。
全バッチ完了後、このファイルからStep 7のMDレポートを生成する。

```json
// screening_judgments.json
[
  { "name": "候補者A", "slug": "...", "judgment": "合格", "reason": "...", "skills": [...], "batch": 1 },
  { "name": "候補者B", "slug": "...", "judgment": "不合格", "reason": "...", "skills": [...], "batch": 1 },
  ...
]
```

---

### 判定基準（Opusサブエージェントへの参考情報）

#### 要件1: 日本国籍であること

名前（漢字・カタカナ等）、所在地（日本）、学歴（日本の教育機関）、プロフィール言語（日本語）で総合判断。
明らかに非該当の場合のみ「不合格」。微妙な場合は「判定保留」。

#### 要件2: Webエンジニアとして2〜3年以上の経験

職歴から累計経験年数を算出する。
- 2年未満 → 不合格
- 職歴確認不能 → 判定保留

**注意:** 以下はWebエンジニアとして扱わない：
- プロフィールにWeb技術記載のない組み込み開発・ITコンサル・PMO

**重要:** SIer企業（NRI, NTTデータ等）在籍でも、**プロフィールにWeb技術記載があればOK**。
会社名やタイトルだけで自動不合格にしない。

#### 要件3: フルスタック経験（サーバーサイド + フロントエンド）

**サーバーサイド経験:** バックエンド言語/フレームワーク・DB・API設計・インフラいずれかの経験

**フロントエンド経験:** React/Vue/Angular等フレームワーク・TypeScript+フロント文脈・HTML/CSS実務経験

**判定ルール:**
- スキルセクションに両サイドの技術 → 合格
- ヘッドラインに "Full-Stack" 明記 → 合格
- モバイル（iOS/Android/Flutter）はフロントエンドとして扱わない
- SRE/DevOpsのみ（Go + Kubernetes等）はフルスタックとは見なさない
- TypeScript単体ではフロントエンド確定とはしない

#### 判定の基本方針

- 確実に要件を満たさない場合のみ「不合格」
- 情報不足（プロフィール確認済みの上で）→「判定保留」
- 曖昧なケースは合格寄りに判断
- 「判定保留」はプロフィールを開いて全セクション確認した上でも情報が足りない場合のみ

---

## Step 7: 結果の出力

全バッチの判定完了後、`screening_judgments.json` から最終レポートを生成する。

**ファイル名:** `screening_結果_{リスト名}_YYYY-MM-DD.md`（リスト名 + 当日の日付）
**保存先:** `/Users/mor/co-work/採用/`

**重要:** ファイル名にリスト名を含めること。同日に複数のスクリーニングを実施する場合（例: 若手エンジニアとスタジオテックリード）にファイルが衝突するのを防ぐ。

```markdown
# リクルートマーカー スクリーニング結果

- 実施日: YYYY-MM-DD
- 対象リスト: [リスト名]
- リストURL: [リクルートマーカーのリストURL]
- 対象人数: XX名
- 要件非該当: XX名
- 判定保留: XX名
- 合格: XX名

---

## 要件非該当の候補者

### 1. [候補者名]
- **リクルートマーカー**: [リストURL]
- **プロフィールURL**: [LinkedIn/YouTrustのURL]
- **現職**: [リクマ上の会社名・職種]
- **確認された技術スタック**: [プロフィールから確認できた技術]
- **不合格理由**:
  - [具体的な理由]

---

## 判定保留の候補者

### 1. [候補者名]
- **リクルートマーカー**: [リストURL]
- **プロフィールURL**: [LinkedIn/YouTrustのURL]
- **現職**: [リクマ上の会社名・職種]
- **確認された技術スタック**: [確認できた技術]
- **保留理由**:
  - [理由]

---

## 要件合格の候補者（参考）

| # | 候補者名 | プロフィールURL | 主な技術スタック | 備考 |
|---|----------|----------------|-----------------|------|
| 1 | [名前]   | [URL]          | [React, Go 等]  | [メモ] |
```

---

## Step 8: 完了報告

結果ファイル保存後、チャットで以下を報告する：

- 対象リスト名
- 対象人数 / 要件合格 / 要件非該当 / 判定保留の内訳
- 不合格の主な理由の傾向
- 結果ファイルのパス

**Slack通知は送らない。** ユーザーが明示的に依頼した場合のみ送信する。

---

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| リクルートマーカーの未ログイン | Playwrightブラウザでのログインをガイド |
| YouTrustの未ログイン | Playwrightブラウザでのログインをガイド |
| LinkedInのCAPTCHA表示 | ユーザーに報告・YouTrustへ切り替え |
| LinkedInで `browser_snapshot` が空 | `browser_evaluate` + `document.querySelector('main').innerText` に切り替え（これが正規手順） |
| プロフィールが非公開 | 「プロフィール非公開のため判定不能」として記録 |
| Playwright MCPの接続エラー | `browser_tabs` で状態確認・再接続を試みる |
| セッション切れ（再ログインが必要） | 再ログインフロー（Step 1-3 / Step 2-3）へ |
| コンテキスト溢れ・コンパクション発生 | `screening_progress.json` を読んで未処理の候補者から再開。`candidates_raw.json` と `candidates_profiles.json` は既に保存済みなので再収集不要 |
| Writeツールで「File has not been read yet」エラー | 新規ファイルでもまず `Read` を実行（存在しないエラーが返る）→ その後 `Write` を実行 |
| 同名ファイルが既に存在 | ファイル名にリスト名を含める命名規則（Step 7参照）で衝突を防ぐ。それでも衝突する場合は末尾に `_2` を付加 |

## セッション管理のメモ

Playwright MCPはサーバープロセスが起動している間、ブラウザコンテキスト（Cookie含む）を保持する。
MCP再起動後は再ログインが必要になる場合がある。

セッションキャッシュは `/Users/mor/co-work/採用/.session_cache/` に保存される（localStorage/sessionStorageのみ）。
HttpOnly Cookieは保存できないため、ログイン維持にはPlaywright MCPの継続稼働が最も確実。
