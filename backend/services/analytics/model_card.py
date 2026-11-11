"""What the student risk scoring is, written so that someone checking it is not misled.

The wording here is the app's own statement about its models. Keep it true to ai-ml/predictions: if a model's inputs or labels change,
change this in the same commit (tests/test_risk_model_card.py checks the inputs it lists against the code).
"""

MODEL_CARD = {
    'title': 'How the student risk scores are made',
    'summary': (
        'The scores are advice for staff, not a prediction of what will happen to a student. They are produced by models that were fitted '
        'to fixed, written scoring rules, so they reproduce those rules. They were not learned from recorded outcomes such as students '
        'who actually left or families who actually defaulted, and they have not been checked against real outcomes.'
    ),
    'models': [
        {'name': 'Dropout risk', 'algorithm': 'XGBoost classifier',
         'inputs': ['Attendance rate', 'Average exam percentage', 'Number of behaviour or concern notes'],
         'rule': 'Labelled "at risk" when 0.5 x (1 - attendance) + 0.3 x (1 - exam average) + 0.1 x behaviour notes is above 0.45.'},
        {'name': 'Fee-default risk', 'algorithm': 'Logistic regression',
         'inputs': ['Share of the amount billed that is past its due date and unpaid'],
         'rule': 'Labelled "at risk" when 40% or more of what was billed is overdue and unpaid. Invoices not yet due do not count.'},
        {'name': 'Grade band', 'algorithm': 'Random forest classifier',
         'inputs': ['Attendance rate', 'Average exam percentage', 'Unpaid balance'],
         'rule': 'Labelled high when the exam average is under 55% or attendance under 70%; medium under 70% or 80%, or an unpaid balance over 40,000.'},
        {'name': 'Attendance anomalies', 'algorithm': 'Isolation forest',
         'inputs': ['Absence rate', 'Late rate', 'Longest run of absences', 'Monday absence rate'],
         'rule': 'Set to flag the 15% of students whose attendance differs most from the rest, so about 15% are always flagged, however good the attendance.'},
    ],
    'training_data': (
        'Each school is scored by models fitted on that school\'s own student records plus about 150 to 200 generated example rows that follow the '
        'same rules, added so a small school can still be scored. Labels for the school\'s own students come from the same rules.'
    ),
    'levels': 'Low, medium, high and critical come from fixed cut-offs on the dropout and fee-default scores (25, 50 and 75). A high or critical flag waits for a person to review it.',
    'not_used': ['Gender', 'Ethnicity or nationality', 'Family income', 'Number of siblings', 'Address or neighbourhood', 'Disability or health notes'],
    'missing_data': (
        'When a student has no attendance records, an attendance rate of 92% is assumed (90% for the grade band); with no exam results, 78% '
        '(75% for the grade band). Such scores say so in the list ("data gaps"). Holidays are not counted, and late, early-dismissal and '
        'excused days count as attended.'
    ),
    'limits': [
        'No accuracy figures: with no recorded outcomes there is nothing to measure accuracy against.',
        'Scores move with the rules above. If a rule is a poor fit for your school, the scores will be too.',
        'Small schools and new schools have few records, so most of what the models learn comes from the generated rows.',
        'Equal inputs give equal scores. Many students with the same attendance, marks and overdue share will have the same score.',
        'The check of flag rates by group below is a first look only. It cannot show that the flags are fair, or that they are not.',
        'Not independently audited or certified. Education risk scoring is likely to be classed as high-risk AI in some places (for example under the EU AI Act).',
    ],
    'human_review': 'Nothing is done to a student because of a score. A person reviews each high or critical flag and records worth acting on, need more information, or not a concern, with a reason. That decision is saved with their name and time in the verified decision trail.',
}
