# PostgreSQLの内部構造と高速化
日付: 2026-03-27

## 学んだこと
- PostgreSQLの高速化の4つの柱：インデックス、キャッシュ/バッファ、オプティマイザ、MVCC
- SQLの処理フロー：Parser/Analyzer（構文解析/意味解析）→ Rewriting（書き換え）→ Planner/Optimizer（計画作成/最適化）→ Executor（実行）
- データ書き込みフロー：①更新データ→共有バッファ ②操作ログ→WALバッファ ③WAL Writer→WALディスク ④bgwriter/checkpointer→データディスク
- 共有バッファ：テーブル/インデックスのページをキャッシュするメモリ領域。ディスクI/Oなしでデータ取得可能。PostgreSQL 18で非同期I/O機能追加
- WAL（Write Ahead Logging）：データディスクに書く前にログに書くことで可用性を保証。クラッシュ時はWALからデータ復旧可能
- bgwriter：少しずつdirtyデータをディスクに書き込み続ける。checkpointerのI/O負荷を軽減
- checkpointer：共有バッファの全dirtyデータをデータディスクに書き込む
- OSのファイルキャッシュ：bgwriter/checkpointerはまずOSファイルキャッシュに書き込み、その後OSがディスクに書く。fsyncで明示的にディスク同期も可能
- データ操作が速い理由3つ：①ページ単位（8KB）の小さなデータ単位で記録 ②同じページの繰り返し参照はメモリから即座に取得 ③実行計画で最適な読み込み量に抑制

### 高速化に最も効果が高い3要素
- 正しいテーブル設計
- 効果的なインデックス設計
- 効率的なSQL

### 性能ボトルネック3つと対応する設定値

#### メモリ不足による遅延
- **shared_buffers**：共有バッファのサイズ。推奨値はRAMの25%〜40%。読み取りが多く同じデータを繰り返し触る場合に有効。大きくしすぎるとOSキャッシュ領域を圧迫
- **work_mem**：クエリ操作（sort/hash等）に使えるメモリサイズ。クエリ単位ではなく演算単位で使われる。推奨値 WORK/(N×O×W×p×S)
  - WORK：利用可能なRAMの値（OSキャッシュやshared_buffersなどを引いた値）
  - N：同時に走る重いクエリの数、O：1クエリ内のsort/hashノード数、W：並列ワーカー数、p：hash_mem_multiplierの値、S：安全率（1.5くらい）
- **maintenance_work_mem**：VACUUM、CREATE INDEX等で使用されるメモリサイズ。推奨値はメンテナンス用メモリ数/(同時起動ワーカープロセス数+手動VACUUM数)

#### ディスク書き込みの待ち時間
- **max_wal_size**：チェックポイントが走るWALの閾値。書き込み多い場合は8〜64GB、小規模は2〜8GB。ただし復旧時間とトレードオフ
- **checkpoint_timeout**：チェックポイントによる書き込み間隔。書き込み多い場合は15〜60分、小規模は10〜30分

#### 実行計画のズレによるパフォーマンス低下
- **random_page_cost**：ランダムI/Oのコスト見積もり。SSD/NVMe：1.1〜2.0、HDD：3〜4
- **effective_io_concurrency**：OS並列I/Oのさばける度合い。SSD/NVMe：100〜300、HDD：2〜20
- **effective_cache_size**：Plannerのキャッシュサイズ見積もり値（実際に割り当てられるサイズではない）。推奨値はRAMの50%〜75%

### WALの高速化
- WALは順序保証が必要なデータのため非同期I/Oは使えない（PostgreSQL 18の新機能でも対象外）
- 高速化の方法：WALディスクを速いディスクに割り当てる、WALのデータ量を減らす、WALの書き込み回数を減らす
- **synchronous_commit**：WALバッファからWALディスクへの書き込みを同期/非同期にできる設定
  - デフォルト（on）は同期。スタンバイDB構成の場合、マスタDBだけでなくスタンバイDBのWAL複製まで待機
  - 非同期（off）にするとコミット待機なくなり更新速度向上。ただしクラッシュ時にコミットしたデータが失われる可能性あり（壊れることはない）
  - ログデータなど1件失われても問題ないデータ→非同期OK、会計データなど→同期必須。データの性質に合わせて選択

### MVCCの性能を保持するしくみ
- MVCCはデータ更新時に上書きではなく新しい行にデータを追加。古い行は削除された扱い（実際には削除しない）
- これにより読み取りと書き込みの両方の性能に寄与
- ただし古いデータが残り続けるとデータが肥大化し性能劣化→定期的なVACUUM処理が必要
- **autovacuum機能**：VACUUM処理とANALYZE処理を自動で実行
  - VACUUM：更新/削除で発生した不要行（dead tuples）を削除し、肥大化や性能悪化を防ぐ
  - ANALYZE：不要行削除による統計情報のズレを更新して、適切な実行計画を作れるようにする

## 原文・詳細
RDBMSでは前述の問題を回避するためのしくみを持っている。PostgreSQLでは次のしくみを組み合わせて、検索処理、参照処理、複数同時更新処理の高速化を図っている。
・インデックス：全件走査せずに目的のデータに高速アクセスする
・キャッシュ／バッファ：一度読み込んだデータを再利用のために保存する
・オプティマイザ：最もI/Oが少なくなる実行計画を作成する
・MVCC（MultiVersion Concurrency Control）：参照と更新の競合を最小限にし、ロックによる遅延を減らす

## キーワード
PostgreSQL, SQL処理フロー, Parser, Analyzer, Rewriting, Planner, Optimizer, Executor, 共有バッファ, WAL, Write Ahead Logging, WAL Writer, bgwriter, checkpointer, ファイルキャッシュ, ページ, shared_buffers, work_mem, maintenance_work_mem, max_wal_size, checkpoint_timeout, random_page_cost, effective_io_concurrency, effective_cache_size, synchronous_commit, MVCC, VACUUM, ANALYZE, autovacuum, dead tuples, 非同期I/O
