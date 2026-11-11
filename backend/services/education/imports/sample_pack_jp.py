"""The sample Japanese school ("Midori City Wakaba Gakuen", a nine-year compulsory school, grades 1-9) as a data pack.

Same method as ``sample_pack``: ``build()`` makes every file from a fixed random seed and the timetable is made by the real
generator. What is Japanese about it: names written family name first in kanji, the April-March school year in three terms,
grade and class naming (1年1組), six lessons a day with 給食 (school lunch) and 清掃, Japanese holidays, yen without decimals,
fees that are what a public school really collects (school lunch, materials, PTA), and Japanese school events.
All names and numbers are invented.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta

from .sample_pack import R, _timetable, to_csv, school_days  # noqa: F401  (to_csv is re-exported for the builder)

SCHOOL = 'みどり市立 若葉学園 (Wakaba Gakuen)'
YEAR = '2026年度'
PREFIX = 'WK26-'
DOMAIN = 'wakaba-gakuen.example'
TODAY = date(2026, 11, 6)

# (kanji, romaji)
SURNAMES = [('佐藤', 'sato'), ('鈴木', 'suzuki'), ('高橋', 'takahashi'), ('田中', 'tanaka'), ('伊藤', 'ito'), ('渡辺', 'watanabe'), ('山本', 'yamamoto'),
            ('中村', 'nakamura'), ('小林', 'kobayashi'), ('加藤', 'kato'), ('吉田', 'yoshida'), ('山田', 'yamada'), ('佐々木', 'sasaki'), ('山口', 'yamaguchi'),
            ('松本', 'matsumoto'), ('井上', 'inoue'), ('木村', 'kimura'), ('林', 'hayashi'), ('清水', 'shimizu'), ('山崎', 'yamazaki'), ('森', 'mori'),
            ('池田', 'ikeda'), ('橋本', 'hashimoto'), ('阿部', 'abe'), ('石川', 'ishikawa'), ('山下', 'yamashita'), ('中島', 'nakajima'), ('前田', 'maeda'),
            ('藤田', 'fujita'), ('小川', 'ogawa'), ('後藤', 'goto'), ('岡田', 'okada'), ('長谷川', 'hasegawa'), ('村上', 'murakami'), ('近藤', 'kondo'),
            ('石井', 'ishii'), ('斎藤', 'saito'), ('坂本', 'sakamoto'), ('遠藤', 'endo'), ('青木', 'aoki')]
GIVEN_M = [('蓮', 'ren'), ('湊', 'minato'), ('大和', 'yamato'), ('陽翔', 'haruto'), ('樹', 'itsuki'), ('悠真', 'yuma'), ('颯太', 'sota'), ('翔', 'sho'),
           ('健太', 'kenta'), ('拓海', 'takumi'), ('大輝', 'daiki'), ('蒼', 'aoi'), ('律', 'ritsu'), ('晴', 'haru'), ('優斗', 'yuto'), ('駿', 'shun'),
           ('海斗', 'kaito'), ('涼太', 'ryota'), ('一輝', 'kazuki'), ('直樹', 'naoki')]
GIVEN_F = [('陽菜', 'hina'), ('凛', 'rin'), ('結衣', 'yui'), ('芽依', 'mei'), ('紬', 'tsumugi'), ('莉子', 'riko'), ('咲良', 'sakura'), ('葵', 'aoi'),
           ('美咲', 'misaki'), ('花', 'hana'), ('愛菜', 'aina'), ('心愛', 'kokona'), ('彩', 'aya'), ('七海', 'nanami'), ('優奈', 'yuna'), ('楓', 'kaede'),
           ('瑞希', 'mizuki'), ('茜', 'akane'), ('千尋', 'chihiro'), ('遥', 'haruka')]
FATHER = [('一郎', 'ichiro'), ('健一', 'kenichi'), ('誠', 'makoto'), ('学', 'manabu'), ('剛', 'tsuyoshi'), ('浩二', 'koji'), ('哲也', 'tetsuya'), ('智也', 'tomoya'),
          ('隆', 'takashi'), ('修', 'osamu')]
MOTHER = [('恵子', 'keiko'), ('由美', 'yumi'), ('裕子', 'yuko'), ('真理', 'mari'), ('久美子', 'kumiko'), ('美穂', 'miho'), ('香織', 'kaori'), ('直美', 'naomi'),
          ('智子', 'tomoko'), ('舞', 'mai')]
TOWNS = ['緑町', '若葉台', '桜ヶ丘', '朝日町', '栄町', '駅前', '中央', '東町', '西町', '北原']
BLOOD = ['A+', 'B+', 'O+', 'AB+', '']

# (class, code, grade level, sections, monthly school lunch fee in yen)
SEC2, SEC1 = ['1組', '2組'], ['1組']
CLASSES = [('1年', 'G1', 1, SEC2, 4500), ('2年', 'G2', 2, SEC2, 4500), ('3年', 'G3', 3, SEC2, 4500), ('4年', 'G4', 4, SEC1, 4500), ('5年', 'G5', 5, SEC1, 4500),
           ('6年', 'G6', 6, SEC1, 4500), ('7年', 'G7', 7, SEC1, 5300), ('8年', 'G8', 8, SEC1, 5300), ('9年', 'G9', 9, SEC1, 5300)]
# subject name, code, department, elective, lessons a week by stage (grades 1-2, 3-6, 7-9)
SUBJECTS = [('国語', 'JPN', '国語', False, (5, 5, 4)), ('算数・数学', 'MATH', '算数・数学', False, (4, 5, 4)), ('理科', 'SCI', '理科', False, (0, 3, 4)),
            ('社会', 'SOC', '社会', False, (0, 3, 3)), ('生活', 'LIFE', '生活', False, (3, 0, 0)), ('外国語（英語）', 'ENG', '外国語', False, (0, 1, 4)),
            ('音楽', 'MUS', '音楽', False, (2, 2, 1)), ('図画工作・美術', 'ART', '図工・美術', False, (2, 2, 1)), ('体育', 'PE', '体育', False, (3, 3, 3)),
            ('技術・家庭', 'HOME', '技術・家庭', False, (0, 0, 1)), ('特別の教科 道徳', 'MORAL', '道徳', False, (1, 1, 1)),
            ('総合的な学習の時間', 'INQ', '総合', False, (0, 2, 1))]
TEACHERS_PER_SUBJECT = {'JPN': 3, 'MATH': 3, 'SCI': 2, 'SOC': 2, 'LIFE': 1, 'ENG': 1, 'MUS': 1, 'ART': 1, 'PE': 2, 'HOME': 1, 'MORAL': 1, 'INQ': 1}
NON_TEACHING = [('Principal', '管理職'), ('Assistant Principal', '管理職'), ('Office Manager', '事務'), ('School Nurse', '保健室'),
                ('School Counselor', '生徒指導'), ('Librarian', '図書館')]
# closed days (Japanese national holidays, the summer and winter breaks and a school day off)
HOLIDAYS = [('敬老の日', '2026-09-21', '2026-09-21'), ('国民の休日', '2026-09-22', '2026-09-22'), ('秋分の日', '2026-09-23', '2026-09-23'),
            ('スポーツの日', '2026-10-12', '2026-10-12'), ('文化の日', '2026-11-03', '2026-11-03'), ('勤労感謝の日', '2026-11-23', '2026-11-23'),
            ('冬休み', '2026-12-26', '2027-01-07'), ('成人の日', '2027-01-11', '2027-01-11'), ('建国記念の日', '2027-02-11', '2027-02-11'),
            ('天皇誕生日', '2027-02-23', '2027-02-23'), ('春分の日（振替休日）', '2027-03-22', '2027-03-22'), ('春休み', '2027-03-25', '2027-04-05')]
# no lessons in the school year's early part of September are counted: the second term starts on 1 September
START = date(2026, 9, 1)


def stage(grade):
    return 0 if grade <= 2 else 1 if grade <= 6 else 2


def phone(rng):
    return f'090-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}'


def closed_dates():
    out = set()
    for _n, a, b in HOLIDAYS:
        d, e = date.fromisoformat(a), date.fromisoformat(b)
        while d <= e:
            out.add(d)
            d += timedelta(days=1)
    return out


def build(seed=2026):
    """{kind: rows} for the whole pack. Needs a migrated database (a scratch school is made and rolled back)."""
    rng = random.Random(seed)
    files = defaultdict(list)

    # -- academic set-up (the Japanese year runs April to March, in three terms) --------------------------------------------
    files['academic_years'].append(R('academic_years', name=YEAR, start_date='2026-04-06', end_date='2027-03-24', active=True))
    files['terms'] += [R('terms', year=YEAR, name='1学期', kind='trimester', order=1, start_date='2026-04-06', end_date='2026-07-20'),
                       R('terms', year=YEAR, name='2学期', kind='trimester', order=2, start_date='2026-09-01', end_date='2026-12-25'),
                       R('terms', year=YEAR, name='3学期', kind='trimester', order=3, start_date='2027-01-08', end_date='2027-03-24')]
    for name, code, grade, sections, fee in CLASSES:
        files['classes'].append(R('classes', name=name, sections=', '.join(sections), grade_level=grade, capacity=35, tuition_fee=fee, code=code))
    for name, code, dept, elective, _p in SUBJECTS:
        files['subjects'].append(R('subjects', name=name, code=code, department=dept, elective=elective))
    for i in range(1, 13):
        files['rooms'].append(R('rooms', code=f'C{i:02d}', name=f'教室{i}', capacity=36, category='classroom', floor='first' if i <= 6 else 'second', location='本校舎'))
    files['rooms'] += [R('rooms', code='GYM', name='体育館', capacity=200, category='sports', floor='ground', location='体育館棟'),
                       R('rooms', code='FIELD', name='校庭', capacity=200, category='sports', floor='ground', location='屋外'),
                       R('rooms', code='PC', name='コンピュータ室', capacity=40, category='lab', floor='second', location='本校舎'),
                       R('rooms', code='MUSIC', name='音楽室', capacity=40, category='classroom', floor='second', location='特別教室棟'),
                       R('rooms', code='ARTR', name='図工室', capacity=40, category='classroom', floor='first', location='特別教室棟'),
                       R('rooms', code='SCIR', name='理科室', capacity=40, category='lab', floor='first', location='特別教室棟')]
    bell = [('08:45', '09:30'), ('09:40', '10:25'), ('10:45', '11:30'), ('11:40', '12:25'), ('13:20', '14:05'), ('14:15', '15:00')]
    num = 0
    for i, (a, b) in enumerate(bell, 1):
        if i == 3:
            num += 1
            files['periods'].append(R('periods', year=YEAR, number=num, name='中休み', start_time='10:25', end_time='10:45', **{'break': True}))
        if i == 5:
            num += 1
            files['periods'].append(R('periods', year=YEAR, number=num, name='給食・昼休み', start_time='12:25', end_time='13:20', **{'break': True}))
        num += 1
        files['periods'].append(R('periods', year=YEAR, number=num, name=f'{i}限', start_time=a, end_time=b, **{'break': False}))
    for i, day in enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], 1):
        files['weekdays'].append(R('weekdays', day=day, active=True, half_day=False, order=i))
    sec_count = {code: len(sections) for _n, code, _g, sections, _f in CLASSES}
    for name, code, grade, _s, _f in CLASSES:
        for _sn, scode, _d, _e, ppw in SUBJECTS:
            p = ppw[stage(grade)]
            if p:
                files['class_subjects'].append(R('class_subjects', **{'class': name, 'subject': scode, 'periods_per_week': p, 'marks': 100}))

    # -- staff (salary in yen a month) ---------------------------------------------------------------------------------
    pay = [('教諭（若手）', 290000, '経験5年未満'), ('教諭', 340000, '経験5年以上'), ('主幹教諭', 400000, '教科・学年のまとめ役'),
           ('事務職員', 300000, '事務・支援'), ('管理職', 520000, '校長・教頭')]
    for nme, amount, note in pay:
        files['pay_grades'].append(R('pay_grades', name=nme, base_salary=amount, notes=note))
    grade_of = {'young': '教諭（若手）', 'mid': '教諭', 'lead': '主幹教諭', 'office': '事務職員', 'head': '管理職'}
    used = set()

    def person(female=None):
        while True:
            f = rng.random() < 0.5 if female is None else female
            fam, giv = rng.choice(SURNAMES), rng.choice(GIVEN_F if f else GIVEN_M)
            if (fam[0], giv[0]) not in used:
                used.add((fam[0], giv[0]))
                return fam, giv, 'female' if f else 'male'

    staff, eid = [], 0

    def add_staff(role, dept, subject_name, kind='regular', grade='mid'):
        nonlocal eid
        eid += 1
        fam, giv, gender = person()
        staff.append(dict(id=f'WK-E-{eid:03d}', fam=fam, giv=giv, gender=gender, role=role, dept=dept, subject=subject_name, kind=kind, grade=grade_of[grade],
                          joined=date(2026, 4, 1) - timedelta(days=rng.randint(30, 6000))))
        return staff[-1]

    principal = add_staff('Principal', '管理職', '', grade='head')
    assistant = add_staff('Assistant Principal', '管理職', '', grade='head')
    for role, dept in NON_TEACHING[2:]:
        add_staff(role, dept, '', grade='office')
    by_subject = defaultdict(list)
    for sname, scode, dept, _e, _p in SUBJECTS:
        for k in range(TEACHERS_PER_SUBJECT[scode]):
            by_subject[scode].append(add_staff('Teacher', dept, sname, grade='lead' if k == 0 else rng.choice(['young', 'mid'])))
    add_staff('Substitute teacher', '国語・算数', '国語, 算数・数学', kind='relief', grade='young')
    add_staff('Substitute teacher', '理科・社会', '理科, 社会', kind='relief', grade='young')
    for t in staff:
        if t is principal:
            continue
        t['manager'] = principal['id'] if t is assistant or t['dept'] in ('事務', '保健室', '生徒指導', '図書館') else assistant['id']
    for t in staff:
        t['name'] = f'{t["fam"][0]} {t["giv"][0]}'
        t['email'] = f'{t["fam"][1]}.{t["giv"][1]}@{DOMAIN}'
        t['salary'] = {n: a for n, a, _ in pay}[t['grade']]
        files['staff'].append(R('staff', full_name=t['name'], email=t['email'], phone=phone(rng), employee_id=t['id'], role=t['role'], department=t['dept'],
                                subjects=t['subject'], joining_date=t['joined'].isoformat(), gender=t['gender'],
                                date_of_birth=(date(1965, 1, 1) + timedelta(days=rng.randint(0, 11000))).isoformat(), monthly_salary=t['salary'],
                                qualifications='教育学修士' if t['role'] == 'Teacher' and rng.random() < 0.3 else '教員免許状' if t['role'] == 'Teacher' else '',
                                home_address=f'みどり市 {rng.choice(TOWNS)} {rng.randint(1, 9)}-{rng.randint(1, 30)}-{rng.randint(1, 20)}',
                                teacher_type=t['kind'], manager=t.get('manager', '')))

    load = defaultdict(int)
    for name, code, grade, sections, _f in CLASSES:
        for _sn, scode, _d, _e, ppw in sorted(SUBJECTS, key=lambda s: -s[4][1]):
            p = ppw[stage(grade)]
            if not p:
                continue
            need = p * sec_count[code]
            pool = sorted(by_subject[scode], key=lambda t: load[t['id']])
            pick = next((t for t in pool if load[t['id']] + need <= 27), pool[0])
            load[pick['id']] += need
            files['teacher_assignments'].append(R('teacher_assignments', teacher=pick['id'], **{'class': name}, subject=scode, year=YEAR, primary=True))

    # -- students and families (family name first) ---------------------------------------------------------------------
    students, families, nsid = [], [], 0
    for name, code, grade, sections, _fee in CLASSES:
        for section in sections:
            for _ in range(rng.randint(8, 10)):
                nsid += 1
                if families and rng.random() < 0.1:
                    fam = rng.choice([f for f in families if f['grade'] != grade and f['kids'] < 3] or families)
                else:
                    sur = rng.choice(SURNAMES)
                    fam = dict(sur=sur, name=f'{sur[0]}家 ({len(families) + 1})', father=rng.choice(FATHER), mother=rng.choice(MOTHER), phone=phone(rng), phone2=phone(rng),
                               address=f'みどり市 {rng.choice(TOWNS)} {rng.randint(1, 9)}-{rng.randint(1, 30)}-{rng.randint(1, 20)}', grade=grade, kids=0)
                    families.append(fam)
                fam['kids'] += 1
                female = rng.random() < 0.5
                giv = rng.choice(GIVEN_F if female else GIVEN_M)
                born = date(2020 - grade, rng.randint(4, 12), rng.randint(1, 28))        # grade 1 is six turning seven in the school year
                students.append(dict(no=f'{PREFIX}{nsid:03d}', giv=giv, fam=fam, gender='female' if female else 'male', born=born, cls=name, grade=grade,
                                     section=section, admitted=date(2026 - grade + 1, 4, 6) if grade > 1 else date(2026, 4, 6)))
    for s in students:
        f = s['fam']
        files['students'].append(R('students', full_name=f'{f["sur"][0]} {s["giv"][0]}', **{'class': s['cls']}, section=s['section'], student_id=s['no'], gender=s['gender'],
                                   date_of_birth=s['born'].isoformat(), admission_date=s['admitted'].isoformat(), father_name=f'{f["sur"][0]} {f["father"][0]}',
                                   mother_name=f'{f["sur"][0]} {f["mother"][0]}', guardian_phone=f['phone'], address=f['address'], city='みどり市',
                                   blood_group=rng.choice(BLOOD), previous_school=rng.choice(['', '', 'みどり幼稚園', 'ひまわり保育園', 'さくら保育園']), family=f['name']))
        for given, relation, who in ((f['mother'], 'mother', 'M'), (f['father'], 'father', 'F')):
            files['guardians'].append(R('guardians', student=s['no'], first_name=given[0], last_name=f['sur'][0], relationship=relation,
                                        email=f'{f["sur"][1]}.{given[1]}.{s["no"][-3:]}@family.example', mobile_phone=f['phone'] if who == 'M' else f['phone2'],
                                        occupation=rng.choice(['会社員', '看護師', '公務員', '自営業', '教員', 'エンジニア', 'パート']), is_primary=who == 'M',
                                        lives_with=True, has_custody=True, can_pickup=True, is_emergency_contact=True, receives_billing=who == 'M',
                                        receives_messages=True, portal_access=who == 'M', priority=1 if who == 'M' else 2))
    allergies = ['卵', '乳製品', 'そば', 'ピーナッツ', '小麦', 'えび・かに']
    flagged = {x['no'] for x in rng.sample(students, 40)}
    for s in students:
        needs = s['no'] in flagged
        sev = needs and rng.random() < 0.25
        cond = rng.choice(['喘息', 'アトピー性皮膚炎', '']) if needs else ''
        files['student_health'].append(R('student_health', student=s['no'], allergies=rng.choice(allergies) if needs and (sev or rng.random() < 0.7) else 'なし',
                                         severe_allergy=sev, medical_conditions=cond, medications='エピペン' if sev else '吸入薬' if cond == '喘息' else '',
                                         dietary_restrictions='給食の除去食あり' if needs and sev else '', physician_name=f'{rng.choice(SURNAMES)[0]}医院',
                                         physician_phone=phone(rng), emergency_consent=True,
                                         notes='学校と医療機関で対応を共有済み' if sev or cond == '喘息' else ''))

    # -- admissions (next year's first graders and transfers) ------------------------------------------------------------
    stages = ['pending'] * 6 + ['reviewing'] * 6 + ['approved'] * 5 + ['waitlisted'] * 2 + ['withdrawn']
    for i, st in enumerate(stages):
        female = rng.random() < 0.5
        sur, giv = rng.choice(SURNAMES), rng.choice(GIVEN_F if female else GIVEN_M)
        grade = 1 if i < 14 else rng.randint(2, 8)
        files['admissions'].append(R('admissions', full_name=f'{sur[0]} {giv[0]}', email=f'{sur[1]}.family{i}@example.org', phone=phone(rng),
                                     date_of_birth=date(2027 - grade - 6, rng.randint(1, 12), rng.randint(1, 28)).isoformat(), gender='female' if female else 'male',
                                     applying_for_class=CLASSES[grade - 1][0], academic_year='2027年度', status=st,
                                     status_notes={'pending': '就学時健康診断の結果待ち', 'reviewing': '学校見学の予定あり', 'approved': '入学通知を送付', 'waitlisted': '学区外のため調整中',
                                                   'withdrawn': '転居のため辞退'}.get(st, ''), father_name=f'{sur[0]} {rng.choice(FATHER)[0]}', father_phone=phone(rng),
                                     mother_name=f'{sur[0]} {rng.choice(MOTHER)[0]}', mother_phone=phone(rng), previous_school=rng.choice(['みどり幼稚園', 'ひまわり保育園']),
                                     address=f'みどり市 {rng.choice(TOWNS)} {rng.randint(1, 9)}-{rng.randint(1, 30)}-{rng.randint(1, 20)}', city='みどり市'))

    # -- fees: what a public school collects (school lunch, materials, PTA), in yen ------------------------------------------
    for name, code, grade, sections, fee in CLASSES:
        files['fee_structure'].append(R('fee_structure', **{'class': name}, fee_name='給食費', amount=fee, due_date='2026-09-27', academic_year=YEAR, recurring=True,
                                        frequency='monthly'))
        files['fee_structure'].append(R('fee_structure', **{'class': name}, fee_name='教材費・PTA会費', amount=3000, due_date='2026-05-31', academic_year=YEAR,
                                        recurring=False, frequency='yearly'))
    fees = {c[0]: c[4] for c in CLASSES}
    inv, rc = 0, 0
    for month, due, issued, paid_share in (('09', '2026-09-27', '2026-09-01', 0.93), ('10', '2026-10-27', '2026-10-01', 0.88)):
        for s in students:
            inv += 1
            amount = fees[s['cls']]
            number = f'WKG-INV-2026-{month}-{inv:04d}'
            files['invoices'].append(R('invoices', invoice_number=number, student=s['no'], invoice_type='tuition', amount=amount, opening_balance=0, discount_amount=0,
                                       late_fee_amount=0, due_date=due, issue_date=issued, status='issued', description=f'{int(month)}月分 給食費'))
            roll = rng.random()
            if roll < paid_share:
                rc += 1
                files['payments'].append(R('payments', invoice=number, reference=f'WKG-RCPT-26-{rc:04d}', amount=amount, payment_date=f'2026-{month}-{rng.randint(10, 26):02d}',
                                           payment_method=rng.choice(['bank_transfer', 'bank_transfer', 'cash']), notes='口座振替'))
    for s in rng.sample(students, 5):
        files['balances'].append(R('balances', student_id=s['no'], amount=rng.choice([3000, 6000, 9000]), due_date='2026-10-31', description='前年度未納分（給食費）'))

    # -- pay and leave -----------------------------------------------------------------------------------------------
    for t in staff:
        files['payroll_profiles'].append(R('payroll_profiles', employee=t['id'], pay_grade=t['grade'], tax_rate_percent=8,
                                           benefits='健康保険:18000:deduction; 厚生年金:32000:deduction' + ('; 通勤手当:10000:allowance' if t['role'] == 'Teacher' else '')))
        for month in ('2026-09-01', '2026-10-01'):
            tax = round(t['salary'] * 0.08)
            paid = month == '2026-09-01'
            files['payslips'].append(R('payslips', employee=t['id'], month=month, basic_salary=t['salary'], allowances=10000 if t['role'] == 'Teacher' else 0,
                                       deductions=50000 + tax, paid_amount=t['salary'] + (10000 if t['role'] == 'Teacher' else 0) - 50000 - tax if paid else 0,
                                       payment_date='2026-09-25' if paid else '', payment_method='bank_transfer' if paid else ''))
        files['leave_balances'].append(R('leave_balances', employee=t['id'], sick=10, casual='', annual=20, personal=3, bereavement=5, jury=3, professional=5,
                                         carried_over=rng.choice([0, 5, 10, 20])))
    teachers = [t for t in staff if t['role'] == 'Teacher']
    leaves = [(teachers[0], 'sick', '2026-11-10', '2026-11-11', 'approved', 'インフルエンザ'), (teachers[3], 'annual', '2026-10-23', '2026-10-23', 'approved', '年次有給休暇'),
              (teachers[6], 'professional', '2026-11-05', '2026-11-05', 'approved', '研修（教育委員会）'), (teachers[1], 'sick', '2026-10-14', '2026-10-15', 'approved', '通院'),
              (teachers[8], 'annual', '2026-11-16', '2026-11-18', 'pending', '年次有給休暇'), (teachers[11], 'bereavement', '2026-10-19', '2026-10-21', 'approved', '忌引')]
    for t, kind, a, b, status, reason in leaves:
        files['leave_requests'].append(R('leave_requests', employee=t['id'], leave_type=kind, start_date=a, end_date=b, day_part='full', status=status, reason=reason))

    # -- the term so far: attendance, exams, calendar ---------------------------------------------------------------------
    closed = closed_dates()
    days = list(school_days(START, TODAY, closed))
    ill = ['illness', 'illness', 'illness', 'medical', 'family']        # the importer's fixed list of reasons
    for d in days[-20:]:
        for s in students:
            r = rng.random()
            if r < 0.955:
                status, reason, exc, late = 'present', '', False, ''
            elif r < 0.985:
                status, reason, exc, late = 'absent', rng.choice(ill), rng.random() < 0.7, ''
            else:
                status, reason, exc, late = 'late', 'transport', False, rng.choice([5, 10, 15])
            files['attendance'].append(R('attendance', student=s['no'], date=d.isoformat(), status=status, reason=reason, excused=exc, minutes_late=late))
    for d in days[-12:]:
        for t in staff:
            files['staff_attendance'].append(R('staff_attendance', employee=t['id'], date=d.isoformat(), status='present'))
    code = 0
    for name, ccode, grade, sections, _f in CLASSES:
        for subj, total, passing, title, when in (('MATH', 100, 50, '単元テスト', '2026-10-09'), ('JPN', 100, 50, '漢字テスト', '2026-10-02')):
            code += 1
            ec = f'WKG-EXM-2026-{code:04d}'      # exam codes and receipt numbers are unique across all schools, so this school has its own prefix
            files['exams'].append(R('exams', exam_code=ec, title=f'{name} {title}', exam_type='test', **{'class': name}, subject=subj, total_marks=total,
                                    passing_marks=passing, exam_date=when, academic_year=YEAR, term='second', is_published=True, is_active=True))
            for s in [x for x in students if x['cls'] == name]:
                files['exam_results'].append(R('exam_results', exam=ec, student=s['no'], obtained_marks=max(0, min(total, round(rng.gauss(total * 0.76, total * 0.15))))))
    for nme, a, b in HOLIDAYS:
        files['calendar_events'].append(R('calendar_events', title=nme, kind='holiday', start_date=a, end_date=b, audience='everyone', closes_school=True, description='休み'))
    files['calendar_events'] += [R('calendar_events', title='運動会', kind='event', start_date='2026-10-10', end_date='2026-10-10', location='校庭', audience='everyone',
                                   description='雨天の場合は翌週に延期'),
                                 R('calendar_events', title='遠足', kind='event', start_date='2026-10-22', end_date='2026-10-22', audience='families'),
                                 R('calendar_events', title='学習発表会', kind='event', start_date='2026-11-14', end_date='2026-11-14', location='体育館', audience='everyone'),
                                 R('calendar_events', title='個人面談', kind='meeting', start_date='2026-11-16', end_date='2026-11-20', audience='families',
                                   description='午後の短縮授業'),
                                 R('calendar_events', title='避難訓練', kind='event', start_date='2026-11-27', end_date='2026-11-27', audience='everyone'),
                                 R('calendar_events', title='2学期 終業式', kind='event', start_date='2026-12-25', end_date='2026-12-25', audience='everyone')]

    # -- behaviour / student support -----------------------------------------------------------------------------------------
    cats = [('友だちを助けた', 'positive', 2, 'low', False), ('よく努力した', 'positive', 3, 'low', False), ('リーダーシップ', 'positive', 2, 'low', False),
            ('思いやりのある行動', 'positive', 2, 'low', False), ('授業中の私語', 'negative', -1, 'low', False), ('遅刻', 'negative', -1, 'low', False),
            ('宿題の未提出', 'negative', -1, 'low', False), ('言葉によるトラブル', 'negative', -2, 'medium', True)]
    for i, (nme, kind, pts, sev, notify) in enumerate(cats, 1):
        files['behaviour_categories'].append(R('behaviour_categories', name=nme, kind=kind, points=pts, severity=sev, notify_family=notify, order=i))
    places = ['教室', '校庭', '廊下', '体育館', '図書室']
    text = {'友だちを助けた': '同級生の学習を手伝った', 'よく努力した': '単元のまとめを最後までやりぬいた', 'リーダーシップ': '班活動をまとめた', '思いやりのある行動': '転入生に声をかけた',
            '授業中の私語': '授業中に話してしまった', '遅刻': '始業に間に合わなかった', '宿題の未提出': '宿題が出されていない', '言葉によるトラブル': '友だちにきつい言葉を使った'}
    for d in days[-15:]:
        for s in rng.sample(students, rng.randint(5, 8)):
            nme, kind, pts, sev, _n = rng.choice([c for c in cats if c[1] == 'positive' or rng.random() < 0.25])
            files['behaviour_incidents'].append(R('behaviour_incidents', student=s['no'], category=nme, date=d.isoformat(), time=f'{rng.randint(9, 14):02d}:{rng.choice(["05", "20", "40"])}',
                                                  location=rng.choice(places), description=text[nme], points=pts, severity=sev,
                                                  status='resolved' if kind == 'positive' else rng.choice(['open', 'in_review', 'resolved']), visible_to_family=True,
                                                  action='verbal_warning' if kind == 'negative' and rng.random() < 0.6 else '', action_notes=''))
    for s in rng.sample(students, 12):
        kind = rng.choice(['counselling', 'meeting'])
        files['observations'].append(R('observations', student=s['no'], observation_type=kind, title='スクールカウンセラーとの面談' if kind == 'counselling' else '保護者との面談',
                                       date=rng.choice(days[-20:]).isoformat(), description='学校生活の様子について話し合った。', severity='low', status=rng.choice(['open', 'resolved']),
                                       parent_notified=True, action_taken='定期的に様子を見る', outcome=rng.choice(['', '落ち着いている', '11月に再確認'])))

    files['timetable'] = _timetable_jp(files)
    return dict(files)


def _timetable_jp(files):
    """The base files go into a scratch school and the real generator makes the timetable (same as the US pack, with this year's name)."""
    from . import sample_pack
    old = sample_pack.YEAR
    sample_pack.YEAR = YEAR
    try:
        return _timetable(files)
    finally:
        sample_pack.YEAR = old
