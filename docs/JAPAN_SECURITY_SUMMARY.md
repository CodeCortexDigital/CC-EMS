# CC-EMS: Security and privacy summary for Japan / 日本向け セキュリティとプライバシーの概要

Prepared for: Masato Yamano (Nissho School & Office Inc.), for the call on 10 November 2026. Source: the project's own documents
(`CLIENT_READINESS.md`, `TENANT_ISOLATION_TEST_SUMMARY.md`, `AI_GOVERNANCE.md`, `DISASTER_RECOVERY_PLAN.md`), checked 7 November 2026.
This is a description of what is built and tested. It is **not** a certification and **not** a legal opinion.

---

## English

### What CC-EMS does

| Topic | What is built | How it was checked |
|---|---|---|
| **Each school kept separate** | Every record belongs to one school. The school is taken from the signed-in person on the server, never from the browser. A person from school B cannot list, open, change or delete school A's records. | Automated two-school tests, and a test that fails if a new data table is added without a school-separation decision. |
| **Roles** | Administrator, teacher, parent, student, finance. Each sees only what the role allows. Families see only their own children. Report cards and invoices are downloadable only by the right family or staff. | Automated role tests; direct-address tests. |
| **Sign-in** | Two-step sign-in, sign-in history, limits on repeated attempts and on sign-up. | Built; see the sign-in tests. |
| **Audit trail** | A log of sensitive reads and changes. AI-related records also form a hash-chained trail that shows if a record was altered. | Chain check in the app; automated tests. |
| **AI is advice, not action** | The assistant can only ask. A person approves any action (two different approvers by default). Approval is tied to the exact action and re-checked against current data. Every answer and review leaves a record. One "All AI" switch turns everything off. | `AI_GOVERNANCE.md`; automated tests. |
| **Personal data and AI** | National-ID-type numbers, birth dates and health details are masked before any text is sent to an AI provider. | Automated tests. |
| **Children's data rights** | A school can produce a complete copy of one student's data, and erase one student. Each school sets how long each kind of record is kept; nothing is removed until the school sets a period. | Automated tests. |
| **Backups** | Daily encrypted backups (AES-256), a weekly check of the backup, and a written restore plan (24-hour recovery point). | Scripts and plan in the project; a full test-restore on the hosted demo is still to be done. |

### What is not in place (stated plainly)

- **No independent security audit or penetration test** has been done. The tests are written and run by the team that built the system.
- **No certification** (for example ISO 27001, or listing in Japan's government cloud programme ISMAP). We do not claim compliance with Japan's privacy law (APPI) or with the MEXT education information security guidelines. A review against those documents, with Nissho, is a sensible next step.
- **Hosting is not in Japan.** The demo runs on Render and Vercel with a hosted database. A Japan-region deployment (for example a Tokyo cloud region) would be a configuration and cost decision for a real customer.
- **Schools share one database.** Separation is by a school column and server-side filtering, not by separate databases. A mistake in that layer would affect all schools, which is why the tests above exist. A dedicated database per Board of Education is possible but is not built.
- **AI providers are outside Japan.** The assistant uses OpenAI, Claude or Gemini. Only masked text is sent, and AI can be switched off for a school. Without an API key the assistant runs in a simple local mode.
- **Retention covers most, not all, record types** (library, transport and visitor logs are still manual).
- **Japanese-school features are partly built.** The interface can be shown in Japanese, and a Japanese sample school is included. The Japanese legal pupil record (指導要録) and the Japanese-style term report (通知表) layouts are not built yet.

### Questions a Board of Education is likely to ask

1. Where is the data stored, and can it stay in Japan?
2. Who can see a student's data, and is access recorded?
3. How are children's records deleted when a student leaves?
4. What happens if the service fails: how fast can we restore?
5. Is AI used on student data, and who decides?
6. Has it been audited by a third party?

Our honest answers are in the tables above. Questions 1 and 6 are where we need to work with Nissho.

---

## 日本語

宛先：山野 将人 様（株式会社 Nissho School & Office）／2026年11月10日の打ち合わせ用。出典：当社プロジェクトの文書（2026年11月7日確認）。
本資料は「実装済みの内容とテスト結果」の説明であり、**認証や法的見解ではありません**。

### CC-EMS で実装している内容

| 項目 | 実装内容 | 確認方法 |
|---|---|---|
| **学校ごとのデータ分離** | すべてのデータは1つの学校に属します。学校の判定は、ブラウザではなくサーバー側でログイン中の本人から行います。別の学校の利用者が、他校のデータを一覧・閲覧・変更・削除することはできません。 | 2校を使った自動テスト。新しいデータ表に分離の判断がない場合は失敗するテスト。 |
| **権限（ロール）** | 管理者、教員、保護者、生徒、経理。各ロールは許可された範囲のみ閲覧できます。保護者は自分の子どもの情報のみ見られます。通知表や請求書は、該当する家庭と職員のみがダウンロードできます。 | 権限の自動テスト、URL直接指定のテスト。 |
| **ログイン** | 二段階認証、ログイン履歴、試行回数とサインアップの制限。 | 実装済み。 |
| **監査記録** | 重要な閲覧・変更の記録。AI関連の記録は、改ざんを検知できるハッシュ連鎖の記録としても保存されます。 | アプリ内の整合性チェック、自動テスト。 |
| **AIは助言のみ** | AIアシスタントは「提案」だけを行い、実行には人の承認が必要です（初期設定では別々の2人の承認）。承認は具体的な操作に結びつき、実行時に最新のデータで再確認されます。すべての回答とレビューが記録されます。「AIすべて停止」のスイッチが1つあります。 | `AI_GOVERNANCE.md`、自動テスト。 |
| **個人情報とAI** | 国民ID相当の番号、生年月日、健康情報は、AI事業者にテキストを送る前にマスクされます。 | 自動テスト。 |
| **児童生徒のデータの権利** | 生徒1人分のデータの全件コピーの作成、および1人分の削除ができます。学校ごとに記録の保存期間を設定でき、設定するまでは何も削除されません。 | 自動テスト。 |
| **バックアップ** | 毎日の暗号化バックアップ（AES-256）、週1回のバックアップ検証、復旧手順書（復旧時点目標24時間）。 | スクリプトと手順書あり。ホスト型デモでの完全な復元テストは今後実施予定。 |

### 現時点で未実施・未対応の事項（正直にお伝えします）

- **第三者によるセキュリティ監査・ペネトレーションテストは未実施**です。テストは開発チーム自身が作成・実行しています。
- **各種認証は未取得**です（例：ISO 27001、政府クラウド制度 ISMAP の登録）。個人情報保護法（APPI）や文部科学省の「教育情報セキュリティポリシーに関するガイドライン」への適合を主張するものではありません。御社と一緒に、これらの文書に照らした確認を行うことが次のステップと考えます。
- **ホスティングは日本国内ではありません。** デモは Render と Vercel 上で動作しています。実際の導入先向けに日本リージョン（東京など）で運用するかは、設定と費用の判断になります。
- **学校間で1つのデータベースを共有**しています。分離は「学校の列」とサーバー側のフィルタで行っており、データベースを別々にしているわけではありません。この仕組みに不具合があれば全校に影響するため、上記のテストを用意しています。教育委員会ごとに専用データベースを持つ構成は可能ですが、未構築です。
- **AI事業者は日本国外**です（OpenAI、Claude、Gemini）。送信するのはマスク済みのテキストのみで、学校ごとにAIを停止できます。APIキーがない場合は、簡易的なローカルモードで動作します。
- **保存期間の自動管理は、ほとんどの記録を対象としていますが、すべてではありません**（図書、送迎、来訪者記録は手動）。
- **日本の学校向け機能は一部のみ実装**です。画面は日本語で表示でき、日本の学校を想定したサンプルデータもあります。法定帳簿である指導要録と、日本式の通知表の様式は、まだ実装していません。

### 教育委員会から想定される質問

1. データはどこに保存され、日本国内に置けますか？
2. 誰が児童生徒のデータを見られ、その閲覧は記録されますか？
3. 児童生徒が卒業・転出したとき、記録はどう削除されますか？
4. サービス障害が起きたとき、どのくらいで復旧できますか？
5. 児童生徒のデータにAIを使いますか。誰が判断しますか？
6. 第三者の監査を受けていますか？

上の表が現時点での正直な回答です。1と6については、御社と協力して進める必要があります。
