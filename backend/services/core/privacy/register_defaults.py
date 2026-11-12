"""Starting wording for a school's data handling register (個人情報取扱台帳), in English and Japanese.

Where the school keeps the data and who it is given to depend on the school, so those lines say what to confirm.
Retention for the 指導要録 follows the School Education Act Enforcement Regulations (学籍に関する記録 20 years, 指導に関する記録 5 years)."""

KEYS = ['identity', 'attendance', 'grades', 'record', 'health', 'support', 'family', 'guidance', 'fees', 'staff', 'photos', 'ai', 'logs']
SENSITIVE = {'health', 'support', 'family', 'guidance'}
CONSENT = {'photos', 'health', 'support'}

# name, data_items, purpose, how_collected, retention, shared_with
EN = {
    'identity': ('Student identity and enrolment', 'Name, date of birth, sex, address, guardian names and contact details, previous school.',
                 'Enrolling the student, contacting guardians, running classes and the school register.', 'Admission form filled in by the guardian; updated by the office.',
                 'While enrolled, then as the school retention rule says.', 'Not given to outside parties, except where the law requires (for example the education board).'),
    'attendance': ('Attendance', 'Daily and period attendance, absence reasons, late arrivals, leave notes from guardians.',
                   'Knowing who is at school, safety, the attendance part of the school record, supporting students who miss school.', 'Teachers mark it; guardians report absences.',
                   'Kept with the school record.', 'Not given to outside parties.'),
    'grades': ('Grades and exam results', 'Marks, assessments, teacher comments, report cards.', 'Assessing and reporting learning to students and guardians.',
               'Entered by teachers.', 'Report cards: as the school retention rule says.', 'Guardians and the student only.'),
    'record': ('Cumulative record (指導要録)', 'Student register part (学籍) and guidance part (指導), assessments by subject, conduct, attendance, remarks.',
               'The legal record of each student, used when the student moves to another school or applies for further study.', 'Compiled from school data and completed by the class teacher; sealed by the principal.',
               'Student register part: 20 years. Guidance part: 5 years (School Education Act Enforcement Regulations).', 'Sent to the receiving school when the student transfers or advances.'),
    'health': ('Health information', 'Health check results, allergies, conditions, medicines, nurse visits.', 'Student safety and health care at school.',
               'Guardian forms and health checks; recorded by the nurse.', 'Kept while enrolled, then as the school retention rule says.',
               'Only staff who need it. Not given to outside parties without consent, except in an emergency or where the law requires.'),
    'support': ('Special needs and support plans', 'Support needs, individual education plans, meeting notes.', 'Giving each student the support they need.',
                'Agreed with guardians and recorded by the support teacher.', 'Kept while enrolled, then as the school retention rule says.', 'Only staff who work with the student; others with guardian consent.'),
    'family': ('Family circumstances', 'Household situation, fee support, welfare concerns.', 'Fee support and student welfare.', 'Told to the school by the guardian or recorded by the welfare staff.',
               'Kept while needed.', 'Not given to outside parties, except to protect a child or where the law requires.'),
    'guidance': ('Guidance and behaviour notes', 'Conduct, counselling notes, incident follow-up.', 'Looking after the student and keeping the school safe.', 'Recorded by teachers and counsellors.',
                 'Kept while enrolled, then as the school retention rule says.', 'Only staff who work with the student.'),
    'fees': ('Fees and payments', 'Fee amounts, invoices, payments, school-lunch fees, balances.', 'Billing and receipts.', 'Created by the office from the fee structure.',
             'Accounting records: as the law requires.', 'The payment provider, only where the school has switched online payment on.'),
    'staff': ('Staff records', 'Name, contact details, role, qualifications, contract, leave, pay.', 'Employing and managing staff.', 'Supplied by the staff member; updated by the office.',
              'While employed and as employment law requires.', 'Payroll and authorities as required by law.'),
    'photos': ('Photos and images', 'Photos and videos of students at school events.', 'School newsletters and records of school life.', 'Taken by staff at school events.',
               'As long as the consent stands.', 'Only where the guardian has agreed to publication.'),
    'ai': ('AI assistant', 'Questions staff type to the assistant and the answers. Names and IDs are masked before they are sent to the AI provider.',
           'Drafting and suggesting; a person approves before anything is done.', 'Typed by staff.', 'AI records kept as the school sets.',
           'The AI provider chosen by the school. Confirm in writing that inputs are not used to train its models.'),
    'logs': ('Sign-in and audit records', 'Who signed in, what they viewed or changed, and when.', 'Security and finding out what happened after a problem.', 'Recorded automatically.',
             'As the school sets under Security.', 'Not given to outside parties.'),
}
STORAGE_EN = 'Cloud servers. Confirm the country (in Japan or overseas) in the platform sub-processor list.'

JA = {
    'identity': ('生徒の基本情報・入学', '氏名、生年月日、性別、住所、保護者氏名・連絡先、前在籍校。', '入学手続き、保護者への連絡、学級運営、学籍の管理。', '保護者が記入する入学書類。事務室が更新。',
                 '在学中。その後は学校の保存規程による。', '法令に基づく場合(教育委員会など)を除き、外部へ提供しません。'),
    'attendance': ('出欠', '日々・時間ごとの出欠、欠席理由、遅刻、保護者からの連絡。', '在校状況の把握、安全管理、指導要録の出欠記録、欠席が続く生徒への支援。', '教員が記録。欠席は保護者が連絡。',
                   '指導要録とともに保存。', '外部へ提供しません。'),
    'grades': ('成績・試験結果', '点数、評価、教員のコメント、通知表。', '学習の評価を生徒と保護者に伝えるため。', '教員が入力。', '通知表: 学校の保存規程による。', '保護者と本人のみ。'),
    'record': ('指導要録', '学籍の記録、指導の記録、教科ごとの評価、行動の記録、出欠、所見。', '生徒の法定の公簿。転校・進学の際に使用。', '学校のデータから作成し、担任が記入、校長が確定。',
               '学籍に関する記録: 20年。指導に関する記録: 5年(学校教育法施行規則)。', '転学・進学の際、進学先の学校へ送付。'),
    'health': ('健康情報(要配慮個人情報)', '健康診断の結果、アレルギー、持病、服薬、保健室の利用。', '生徒の安全と健康管理。', '保護者の提出書類と健康診断。養護教諭が記録。', '在学中。その後は学校の保存規程による。',
               '必要な教職員のみ。緊急時と法令に基づく場合を除き、同意なく外部へ提供しません。'),
    'support': ('特別な支援・個別の計画(要配慮個人情報)', '支援の必要性、個別の教育支援計画、会議の記録。', '一人ひとりに必要な支援を行うため。', '保護者と話し合い、支援担当が記録。', '在学中。その後は学校の保存規程による。',
                '担当の教職員のみ。それ以外は保護者の同意がある場合。'),
    'family': ('家庭の状況(要配慮個人情報)', '世帯の状況、就学援助、福祉上の懸念。', '就学援助と生徒の福祉のため。', '保護者からの申し出、または福祉担当が記録。', '必要な間。', '児童の保護や法令に基づく場合を除き、外部へ提供しません。'),
    'guidance': ('生徒指導・行動の記録(要配慮個人情報)', '行動の様子、相談の記録、事案への対応。', '生徒の支援と学校の安全のため。', '教員・カウンセラーが記録。', '在学中。その後は学校の保存規程による。', '担当の教職員のみ。'),
    'fees': ('学費・給食費', '金額、請求書、入金、給食費、残高。', '請求と領収のため。', '事務室が学費表から作成。', '会計帳簿: 法令による。', '学校がオンライン決済を有効にした場合のみ、決済事業者へ。'),
    'staff': ('職員の記録', '氏名、連絡先、職務、資格、契約、休暇、給与。', '職員の雇用と管理。', '本人が提出し、事務室が更新。', '在職中および労働関係法令による。', '給与計算および法令で定める機関。'),
    'photos': ('写真・動画', '学校行事での生徒の写真・動画。', '学校だよりや学校生活の記録。', '行事で教職員が撮影。', '同意が続く間。', '保護者が公開に同意した場合のみ。'),
    'ai': ('AIアシスタント', '教職員がアシスタントに入力した質問と回答。AI事業者へ送る前に氏名とIDは伏せ字にします。', '下書きと提案。実行前に必ず人が承認します。', '教職員が入力。', 'AIの記録は学校の設定による。',
           '学校が選んだAI事業者。入力内容がモデルの学習に使われないことを書面で確認してください。'),
    'logs': ('ログイン・操作の記録', '誰がいつログインし、何を閲覧・変更したか。', 'セキュリティ、問題発生後の原因調査。', '自動で記録。', '「セキュリティ」の設定による。', '外部へ提供しません。'),
}
STORAGE_JA = 'クラウドのサーバー。所在国(日本国内か海外か)は、プラットフォームの委託先一覧で確認してください。'


def rows(lang: str):
    """The starting entries in the chosen language ('ja' for Japanese, anything else English)."""
    ja = (lang or '').lower().startswith('ja')
    table, storage = (JA, STORAGE_JA) if ja else (EN, STORAGE_EN)
    out = []
    for i, key in enumerate(KEYS):
        name, items, purpose, how, retention, shared = table[key]
        out.append({'key': key, 'name': name, 'data_items': items, 'purpose': purpose, 'how_collected': how, 'retention': retention,
                    'shared_with': shared, 'storage_location': storage, 'sensitive': key in SENSITIVE, 'needs_consent': key in CONSENT, 'position': i})
    return out
