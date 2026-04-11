---
name: junior-engineer-screening
description: |
  リクルートマーカー（app.recruit-marker.jp）で若手エンジニア候補者をスクリーニングするスキル。
  各候補者のLinkedInまたはYouTrustプロフィールを確認し、採用要件（日本国籍、Webエンジニア経験2-3年以上、
  フルスタック経験）に合致しない候補者を理由付きでリストアップする。
  「若手エンジニアのスクリーニング」「候補者をチェックして」「リストのスクリーニングをして」
  「採用候補者をフィルタリング」「リクマのリストを確認」「候補者を絞り込んで」
  「スクリーニングして」「リクルートマーカーで確認」「採用リストのチェック」
  「エンジニア候補の選別」「若手エンジニアリストを確認」
  といったリクエストで必ずこのスキルを使うこと。リクルートマーカー、リクマ、採用スクリーニング、
  候補者チェック、若手エンジニア選考に関する作業では常にこのスキルを起動する。
---

# 若手エンジニア候補者スクリーニング

リクルートマーカー（https://app.recruit-marker.jp/）上の候補者リストに対して、
LinkedIn / YouTrust のプロフィール情報をもとに採用要件チェックを行い、
要件に合致しない候補者を理由付きでリストアップするスキル。

## 前提条件

- Chrome ブラウザが利用可能であること（Claude in Chrome の MCP ツールを使用）
- リクルートマーカーにログイン済みの状態であること
- LinkedIn にもログイン済みであることが望ましい（プロフィールの閲覧制限を緩和できる）

## ワークフロー概要

```
1. リクルートマーカーにアクセス → ログイン確認
2. 作業リストの特定（URLまたはリスト名）
3. リストのグリッドからLinkedIn/YouTrustリンク＋リスト上のテキスト情報を収集
4. 各候補者のプロフィールを閲覧 → スキル・言語・技術スタックを抽出 → チェック要件で判定
5. 結果をマークダウンファイルに出力
6. Slackで完了通知
```

---

## Step 1: リクルートマーカーへのアクセスとログイン確認

Chrome ブラウザツールで対象のリストURLに直接アクセスする。
ユーザーがURLを指定していれば（例: `https://app.recruit-marker.jp/list/person-list/62064`）そのまま使う。

### ログイン状態の確認

ページを開いたらまずログイン状態を確認する。リスト画面が表示されればログイン済み。
ログイン画面にリダイレクトされた場合は、ユーザーに再ログインを依頼する。

---

## Step 2: 作業リストの特定

ユーザーがリストURLやリスト名を指定していれば、そのリストに移動する。
指定がない場合はユーザーに「どのリストで作業しますか？」と確認する。

---

## Step 3: リストからリンク情報の収集

### リクルートマーカーのUI構造

リスト画面はグリッド（テーブル）形式で候補者が表示される。
**重要: このリストは仮想化（virtualized）されており、画面に見えている要素だけがDOMに存在する。**
スクロール位置によって表示される候補者が入れ替わるため、スクロールしながら段階的にデータを収集する必要がある。

各候補者のグリッド行には以下のリンクが含まれる（候補者によって異なる）：
- Google検索リンク（`google.co.jp/search?q=名前+会社名`）
- **LinkedInリンク**（`linkedin.com/in/...`）
- **YouTrustリンク**（`youtrust.jp/users/...`）
- FacebookやGitHubリンク（ある場合）

**また、リスト上の各候補者には以下のテキスト情報が表示されている（スクリーニングの重要な情報源）：**
- 現在の会社名
- 現在の職種/タイトル
- ヘッドライン（LinkedInから取得された概要テキスト。スキル名や技術名が含まれることが多い）

表示件数を100件に設定して一覧を取得する。100件以上ある場合はページネーションで次ページも処理する。

### リンクの収集手順（JavaScript一括収集方式）

仮想化リストに対応するため、`javascript_tool` を使ってスクロールしながらリンクを蓄積する。

**手順：**

1. ページトップにスクロール
2. `javascript_tool` で `window.__allCandidates = {}` を初期化
3. 以下のJavaScriptで現在DOMにある候補者のリンクとテキスト情報を収集：

```javascript
const links = [...document.querySelectorAll('a[href]')];
links.forEach(link => {
  const href = link.href;
  let type = null;
  if (href.includes('linkedin.com/in/')) type = 'linkedin';
  else if (href.includes('youtrust.jp/users/')) type = 'youtrust';
  else return;
  // 親行からテキスト情報を取得
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

4. `scroll` で下に8ティックほどスクロール
5. 上記JavaScriptを再実行（`window.__allCandidates` に蓄積される）
6. 全候補者分のリンクが集まるまで 4-5 を繰り返す（目安: 総数と一致するまで）
7. 最後に全データを出力

**収集時の注意：**
- `lines` 配列の中に会社名・タイトル・ヘッドラインテキストが含まれる。これはStep 5の判定で活用する。
- 1人の候補者がLinkedInとYouTrust両方のリンクを持つ場合、別々のslugとして収集されるため、後で名前ベースでマージする。

---

## Step 4: 候補者のプロフィール確認とスキル・技術スタック抽出

各候補者のプロフィールを1人ずつ確認していく。
新しいタブで各プロフィールを開き、**特にスキル・言語・技術スタック情報を重点的に確認する**。

### プロフィール情報源の優先順位

**YouTrustを最優先で使う。** テスト結果から、YouTrustはLinkedInより圧倒的に情報が豊富であることがわかっている：
- 職歴の会社名・役職・期間が詳細に取得可能
- **スキルタグが明確にリストされている（例: "Go", "Kubernetes", "React" 等）**
- **自己紹介テキストにSkills一覧や技術スタックが書かれていることが多い**
- 各職歴エントリにも使用技術の記載がある場合がある

**LinkedInは補助的に使う。** LinkedInはつながり度合いによって表示内容が制限される：
- 3次以上のつながりの場合、職歴セクションが表示されないことがある
- ヘッドライン（名前の下の1行テキスト）にはスキルや技術名が含まれることが多く有用
- **「スキル」セクションがある場合は必ず確認する（技術スキルが一覧表示される）**
- **「概要（About）」セクションに技術スタックが記載されている場合がある**
- 所在地・学歴は比較的表示されやすい

**情報収集の戦略：**
1. YouTrustリンクがある → YouTrustを開いて `get_page_text` で情報取得
2. YouTrustがなくLinkedInのみ → LinkedInを開いてプロフィール全体を確認
3. どちらもない → リクルートマーカーのリスト上の情報（現職タイトル・会社名・ヘッドライン）のみで判定。情報不足の場合は「判定保留」

### プロフィールの読み取り方法

**YouTrustの場合：**
```
get_page_text でプロフィール全体を取得。以下の情報を重点的に抽出する：

【必須確認項目】
- 自己紹介テキスト内の "Skills" や技術スタック一覧
  → プログラミング言語（Go, Ruby, Python, TypeScript, Java, PHP 等）
  → フレームワーク（Rails, Django, React, Vue, Next.js, Spring 等）
  → インフラ技術（AWS, GCP, Docker, Kubernetes, Terraform 等）
  → データベース（MySQL, PostgreSQL, MongoDB, Redis 等）
- スキルタグ（プロフィール下部に表示される）
- 職歴・学歴（会社名、役職、期間が時系列で表示）
- 各職歴エントリの業務説明に含まれる技術キーワード
```

**LinkedInの場合：**
```
get_page_text でプロフィール全体を取得。以下の情報を重点的に抽出する：

【必須確認項目 - ヘッダーエリア】
- 名前
- ヘッドライン（現職＋スキル名が含まれることが多い）
  → 例: "Full-Stack Engineer | React, Node.js, AWS"
  → 例: "Backend Engineer - Go, Python | PayPay"
- 所在地

【必須確認項目 - 概要（About）セクション】※表示される場合
- 自己紹介文内の技術スタック記載
- 使用言語・フレームワークの列挙

【必須確認項目 - 職歴（Experience）セクション】※表示される場合
- 各職歴の役職名に含まれる技術キーワード
  → "Frontend Engineer", "Backend Developer", "Full-Stack" 等
- 各職歴の説明文に含まれる技術名
  → "React, TypeScript でフロントエンド開発"
  → "Go, gRPC でマイクロサービス構築"

【必須確認項目 - スキル（Skills）セクション】※表示される場合
- LinkedIn上で本人が登録したスキル一覧
  → これが最もフルスタック判定に有用な情報源
  → React, Vue.js 等のフロントエンド技術と
     Go, Ruby, Python 等のバックエンド技術が両方あるか確認

【確認手順】
1. まず get_page_text でページ全体のテキストを取得
2. ヘッドライン・About・Experience・Skills の各セクションから技術キーワードを抽出
3. 職歴が表示されない場合（3次つながり等）は、ページを下にスクロールして
   「スキル」セクションの表示を1回試みる
4. それでも情報が取れなければ、ヘッドラインとリスト上の情報で判定する
```

### 抽出すべき技術キーワード一覧

プロフィールから以下のキーワードを探す。該当するものを全て記録する：

**バックエンド言語・フレームワーク：**
Ruby, Rails, Python, Django, Flask, FastAPI, Go, Golang, Java, Spring, Kotlin,
PHP, Laravel, Node.js, Express, NestJS, Rust, C#, .NET, Elixir, Scala

**フロントエンド技術：**
React, Vue.js, Angular, Next.js, Nuxt.js, Svelte, TypeScript, JavaScript,
HTML, CSS, SCSS, Sass, Tailwind, jQuery, Redux, Zustand

**モバイル（Webフロントエンドとは別扱い）：**
Swift, iOS, Android, Kotlin(モバイル), React Native, Flutter, Dart

**インフラ・DevOps：**
AWS, GCP, Azure, Docker, Kubernetes, Terraform, Ansible, CI/CD,
GitHub Actions, CircleCI, Jenkins, Datadog, Prometheus, Grafana

**データベース：**
MySQL, PostgreSQL, MongoDB, Redis, DynamoDB, Elasticsearch, BigQuery

**その他指標：**
API設計, REST, GraphQL, gRPC, マイクロサービス, SRE, DevOps

### レート制限への配慮

- プロフィール間で2〜3秒の `wait` を入れる（特にLinkedIn）
- LinkedIn のアクセス制限に引っかかった場合（CAPTCHA等）はユーザーに報告
- 一度に大量のLinkedInプロフィールを連続で開かない（10件ごとに少し間を空ける）

---

## Step 5: チェック要件による判定

取得したプロフィール情報（特にスキル・技術スタック情報）を以下の3要件に照らして判定する。

### 要件1: 日本国籍であること

以下の情報から総合的に判断する：
- 名前が日本人名であるか（漢字名、日本語のカタカナ/ひらがな表記など）
- 所在地が日本であるか
- 学歴が日本の教育機関か
- プロフィールが日本語で書かれているか

明らかに日本国籍でないと判断できる場合のみ「不合格」とする。
判断が微妙な場合は「判断保留」として記録し、理由を付記する。

### 要件2: Webエンジニアとして2〜3年以上の経験

職歴やプロフィール情報から、Webエンジニア（ソフトウェアエンジニア、フロントエンドエンジニア、
バックエンドエンジニア、SRE等を含む）としての累計経験年数を算出する。

- 2年未満の場合は「不合格」
- 職歴が確認できない場合は「判定保留」
- リクルートマーカーのリスト上のタイトルも参考にする

**注意：以下はWebエンジニアとして扱わない：**
- SIer企業でのシステムインテグレーター / SE 役割（NRI, CAC, NTTデータ等の受託開発）
- 組み込みソフトウェア開発（NEC, 富士通等のハードウェア部門）
- ITコンサルタント・PMO（アクセンチュア、デロイト等）
- ただし、上記企業でもWeb自社プロダクト開発部門であれば該当する

### 要件3: フルスタック経験（サーバーサイド + フロントエンド）

**プロフィールから抽出したスキル・言語・技術スタック情報を使って判定する。**
職歴のタイトルだけでなく、スキルセクション・自己紹介文・職歴説明に記載された技術を総合的に見る。

**サーバーサイド経験の判定基準（以下のいずれか1つ以上に該当）：**
- バックエンド言語/フレームワークの使用経験: Ruby/Rails, Python/Django/Flask, Go, Java/Spring, PHP/Laravel, Node.js/Express/NestJS, Rust, C#/.NET, Elixir 等
- データベースの実務経験: MySQL, PostgreSQL, MongoDB 等
- API設計/開発の経験: REST, GraphQL, gRPC 等
- インフラ/クラウドの実務経験: AWS, GCP, Docker, Kubernetes 等

**フロントエンド経験の判定基準（以下のいずれか1つ以上に該当）：**
- フロントエンドフレームワークの使用経験: React, Vue.js, Angular, Next.js, Nuxt.js, Svelte 等
- TypeScript/JavaScript を明確にフロントエンド文脈で使用
- HTML/CSS/SCSS の実務レベルの経験

**重要な判定ルール：**
- **スキルセクションに両サイドの技術が明記されている → 合格**
  例: Skills に "React, Vue.js, Go, PostgreSQL" がある → フルスタック
- **ヘッドラインに "Full-Stack" と明記 → 合格**
- **片方のスキルのみ → タイトルや職歴説明で補完情報を探す**
  例: "Frontend Engineer" だが、過去の職歴で "Rails API 開発" の記載あり → 合格寄り
- **モバイル（iOS/Android/Flutter）はフロントエンドとして扱わない**
  → iOS + Rails の場合は「モバイル + バックエンド」であり、Webフロントエンド不在
- **TypeScript 単体ではフロントエンド確定とはしない**（Node.js バックエンドで使うケースがある）
  → TypeScript + React/Vue/Next.js 等の組み合わせならフロントエンド確定
- **SRE/DevOps のみはフルスタックとは見なさない**
  → Go + Kubernetes + Terraform のみ → バックエンド/インフラ寄りで、フロントエンド不在

### 判定の基本方針

- 確実に要件を満たさないと言える場合のみ「不合格」とする
- 情報が不足している場合は「判定保留」とし、人間の確認を促す
- 曖昧なケースでは保守的に判定する（合格寄りに判断）
- **タイトルだけでなく、スキル・言語の記載を必ず確認してから判定する**

---

## Step 6: 結果の出力

全候補者の処理が完了したら、マークダウンファイルを出力する。

### 出力ファイル形式

ファイル名: `screening_結果_YYYY-MM-DD.md`（当日の日付）

```markdown
# リクルートマーカー スクリーニング結果

- 実施日: YYYY-MM-DD
- 対象リスト: [リスト名]
- 対象人数: XX名
- 要件非該当: XX名
- 判定保留: XX名

---

## 要件非該当の候補者

### 1. [候補者名]
- **プロフィールURL**: [LinkedIn/YouTrustのURL]
- **確認したスキル・言語**: [プロフィールから確認できた技術: Go, Python, Kubernetes 等]
- **不合格理由**:
  - [具体的な理由を記載。例: 「スキルにGo, Rust, Kubernetes, Terraformが記載されているがフロントエンド技術（React, Vue等）の記載なし。SRE/インフラ専門と判断」]
  - [複数の要件に引っかかる場合は全て列挙]

### 2. [候補者名]
- **プロフィールURL**: [LinkedIn/YouTrustのURL]
- **確認したスキル・言語**: [プロフィールから確認できた技術]
- **不合格理由**:
  - [理由]

---

## 判定保留の候補者

### 1. [候補者名]
- **プロフィールURL**: [LinkedIn/YouTrustのURL]
- **確認したスキル・言語**: [確認できた範囲の技術。確認不能の場合は「プロフィール非表示のため確認不能」]
- **保留理由**:
  - [具体的な理由。例: 「LinkedInの職歴・スキルセクションが非表示。ヘッドラインは"Backend Engineer"だが、過去のフロントエンド経験の有無が不明」]

---

## 要件合格の候補者（参考）

| # | 候補者名 | プロフィールURL | 確認したスキル・言語 | 備考 |
|---|----------|----------------|---------------------|------|
| 1 | [名前]   | [URL]          | [React, Go, AWS 等] | [簡単なメモ] |
```

### 出力先

結果ファイルはユーザーのワークスペースフォルダに保存し、computer:// リンクで共有する。

---

## Step 7: Slack完了通知

スクリーニング完了後、Slack MCP を使って `#times_morooka`（チャンネルID: `C08L355KPB5`）に通知を送る。

通知メッセージ例：
```
リクルートマーカーのスクリーニングが完了しました。
対象リスト: [リスト名]
対象人数: XX名 / 要件非該当: XX名 / 判定保留: XX名
結果ファイルを確認してください。
```

送信前に `slack_search_users` で "morooka" を検索してユーザーIDを取得し、メンションを付ける。
ユーザーが別の通知先を指定した場合はそちらに送る。

---

## エラーハンドリング

- プロフィールページが閲覧できない場合（非公開等）→「プロフィール非公開のため判定不能」として記録
- リクルートマーカーのセッションが切れた場合 → ユーザーに再ログインを依頼
- LinkedIn でログインが求められた場合 → ユーザーに状況を伝え、対応を依頼
- LinkedIn でCAPTCHA等が表示された場合 → ユーザーに報告し、YouTrustでの確認に切り替え
