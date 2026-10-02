"""Declarative import kinds for the school data pack.

A kind is described once: its model, its columns (with types), and which columns identify a record (its natural key,
for example class name + subject code). From that description we get the check, create, update and export functions,
so a file written by the exporter is exactly what the importer reads.

People write natural keys (class name, student number, employee number), never ids. References to other records are
looked up by those keys, and they only find records of the current school.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal

from django.apps import apps
from django.utils import timezone

from .specs import KINDS, email_ok, norm, parse_bool, parse_date, parse_gender, parse_money, text

# ---------------------------------------------------------------------------------------------------------------- values


def col(key, label, type='text', required=False, aliases=(), field=None, ref=None, choices=None, default=None, export=None):
    """One column. `field` is the model field (default: the key), `ref` the lookup for a reference column,
    `choices` a {value: label} dict for a choice column, `export` a function giving the python value from an object."""
    return {'key': key, 'label': label, 'type': type, 'required': required, 'aliases': list(aliases), 'field': field or key,
            'ref': ref, 'choices': choices, 'default': default, 'export': export}


LOOKUPS = {}      # name -> function(ctx) giving {normalised key: object}
REF_NAME = {}     # name -> function(object) giving the text people write for it


def lookup(name):
    """Register a lookup: `@lookup('class')` on a function returning (dict of key->object)."""
    def wrap(fn):
        LOOKUPS[name] = fn
        return fn
    return wrap


def ref_name(name):
    def wrap(fn):
        REF_NAME[name] = fn
        return fn
    return wrap


def find_ref(ctx, name, raw):
    k = 'lk:' + name
    if k not in ctx:
        ctx[k] = LOOKUPS[name](ctx)
    return ctx[k].get(norm(text(raw)))


def parse_time(v):
    if v in (None, ''):
        return None, None
    if isinstance(v, time):
        return v, None
    if isinstance(v, datetime):
        return v.time(), None
    s = text(v)
    for fmt in ('%H:%M', '%H:%M:%S', '%I:%M %p', '%I:%M%p'):
        try:
            return datetime.strptime(s, fmt).time(), None
        except ValueError:
            pass
    return None, f'"{s}" is not a time (use 08:30)'


def parse_int(v, label):
    if v in (None, ''):
        return None, None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = text(v)
    if re.fullmatch(r'-?\d+', s):
        return int(s), None
    return None, f'{label}: "{s}" should be a whole number'


def parse_decimal(v, label):
    """A plain decimal that may be negative or a percentage (unlike money)."""
    if v in (None, ''):
        return None, None
    s = re.sub(r'[,\s%]', '', text(v))
    try:
        return Decimal(s), None
    except Exception:
        return None, f'{label}: "{text(v)}" is not a number'


def parse_value(c, raw, ctx):
    """(python value, error) for one cell."""
    t, label = c['type'], c['label']
    empty = raw is None or text(raw) == ''
    if empty:
        return c['default'], None
    if t == 'text':
        return text(raw), None
    if t == 'int':
        return parse_int(raw, label)
    if t == 'money':
        return parse_money(raw, label)
    if t == 'decimal':
        return parse_decimal(raw, label)
    if t == 'date':
        v, e = parse_date(raw)
        return v, (f'{label}: {e}' if e else None)
    if t == 'time':
        v, e = parse_time(raw)
        return v, (f'{label}: {e}' if e else None)
    if t == 'bool':
        return parse_bool(raw), None
    if t == 'gender':
        v, e = parse_gender(raw)
        return v or None, e
    if t == 'choice':
        wanted = norm(text(raw))
        for value, name in c['choices'].items():
            if wanted in (norm(value), norm(name)):
                return value, None
        return None, f'{label}: "{text(raw)}" should be one of {", ".join(str(n) for n in c["choices"].values())}'
    if t == 'list':
        return [p.strip() for p in re.split(r'[,;]', text(raw)) if p.strip()], None
    if t == 'ref':
        obj = find_ref(ctx, c['ref'], raw)
        if obj is None:
            return None, f'{label} "{text(raw)}" does not exist (import it first, or check the spelling)'
        return obj, None
    raise ValueError(f'unknown column type {t}')


def cell_text(value, c):
    """How a python value is written in a file."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime('%H:%M')
    if isinstance(value, Decimal):
        s = format(value, 'f')
        return s.rstrip('0').rstrip('.') if '.' in s else s
    if isinstance(value, float):
        return format(Decimal(str(value)), 'f')
    if isinstance(value, (list, tuple)):
        return ', '.join(str(v) for v in value)
    if c['type'] == 'choice' and value in (c['choices'] or {}):
        return str(value)
    if hasattr(value, '_meta'):
        return REF_NAME[c['ref']](value) if c['ref'] else str(value)
    return str(value)


# --------------------------------------------------------------------------------------------------------- the builder


def model_kind(*, label, order, help, model, cols, key, example, filename, depends=(), tier=1, noun=None, queryset=None,
               validate=None, defaults=None, after_create=None, after_update=None, no_update=(), order_by=None,
               before_create=None, finish=None, singular=None, silent=False):
    """Build a complete import kind from a description. `key` lists the column keys that identify a record."""
    app_label, model_name = model.split('.')
    singular = singular or noun or label.rstrip('s').lower()
    by_key = {c['key']: c for c in cols}
    key_cols = [by_key[k] for k in key]

    def Model():
        return apps.get_model(app_label, model_name)

    def has_tenant():
        try:
            Model()._meta.get_field('tenant')
            return True
        except Exception:
            return False

    def all_objects(ctx):
        qs = queryset(ctx) if queryset else Model().objects.all()
        return qs

    def obj_value(c, obj):
        if c['export']:
            return c['export'](obj)
        return getattr(obj, c['field'])

    def key_of_clean(clean):
        return tuple(norm(cell_text(clean.get(c['field']), c)) for c in key_cols)

    def key_of_obj(obj):
        return tuple(norm(cell_text(obj_value(c, obj), c)) for c in key_cols)

    def existing(ctx):
        k = 'existing:' + model
        if k not in ctx:
            ctx[k] = {key_of_obj(o): o for o in all_objects(ctx)}
            ctx['seen:' + model] = set()
        return ctx[k]

    def check(row, ctx):
        errors, clean, given = [], {}, set()
        for c in cols:
            raw = row.get(c['key'])
            value, err = parse_value(c, raw, ctx)
            if err:
                errors.append(err)
            elif c['required'] and (value is None or value == '' or value == []):
                errors.append(f'{c["label"]} is missing')
            clean[c['field']] = value
            if raw is not None and text(raw) != '':
                given.add(c['field'])
        note = ''
        duplicate = ''
        have = existing(ctx)
        seen = ctx['seen:' + model]
        if not errors:
            if validate:
                extra = validate(clean, ctx)
                if isinstance(extra, tuple):
                    extra, note = extra
                errors.extend(extra or [])
        k = key_of_clean(clean)
        if not errors and all(part for part, c in zip(k, key_cols) if c['required']) and any(k):
            if k in have:
                duplicate = f'{singular.capitalize()} {" / ".join(cell_text(clean.get(c["field"]), c) for c in key_cols)} already exists'
            elif k in seen:
                errors.append(f'{" / ".join(cell_text(clean.get(c["field"]), c) for c in key_cols)} appears twice in the file')
            seen.add(k)
        clean['_given'] = given
        clean['_key'] = k
        return clean, errors, duplicate, note

    def create(clean, ctx):
        fields = {f.name for f in Model()._meta.concrete_fields}
        data = {k: v for k, v in clean.items() if k not in ('_given', '_key')}   # helper columns (_g_..) reach before_create
        if defaults:
            for k, v in (defaults(ctx) if callable(defaults) else defaults).items():
                data.setdefault(k, v)
        if before_create:
            data = before_create(data, ctx) or data
        data = {k: v for k, v in data.items() if k in fields}
        data = {k: (v if v is not None or Model()._meta.get_field(k).null else Model()._meta.get_field(k).get_default()) for k, v in data.items()}
        if has_tenant():
            data['tenant'] = ctx['school']
        if silent:   # loading records must not email or notify families; the save signals look for this flag
            obj = Model()(**data)
            obj._silent = True
            obj.save()
        else:
            obj = Model().objects.create(**data)
        if after_create:
            after_create(obj, clean, ctx)
        return obj

    def update(clean, ctx):
        obj = existing(ctx).get(clean['_key'])
        if obj is None:
            return None
        skip = set(no_update) | {c['field'] for c in key_cols}
        changed = False
        fields = {f.name for f in Model()._meta.concrete_fields}
        for c in cols:
            f = c['field']
            if f in skip or f not in clean['_given'] or f not in fields:
                continue
            value = clean[f]
            if getattr(obj, f) != value:
                setattr(obj, f, value)
                changed = True
        if changed:
            obj.save()
        if after_update:
            after_update(obj, clean, ctx)
        return obj

    def export(ctx):
        qs = all_objects(ctx)
        if order_by:
            qs = qs.order_by(*order_by)
        return [[cell_text(obj_value(c, o), c) for c in cols] for o in qs]

    spec = {
        'label': label, 'order': order, 'help': help, 'filename': filename, 'depends': list(depends), 'tier': tier,
        'columns': [(c['key'], c['label'], c['required'], c['aliases']) for c in cols],
        'example': example, 'check': check, 'create': create, 'update': update, 'export': export, 'finish': finish,
        'key': list(key), 'model': model, 'cols': cols,
    }
    return spec


def register(kind, spec):
    KINDS[kind] = spec
    return spec


# ------------------------------------------------------------------------------------------------- shared lookups

def _by(model, *fields, school_only=True):
    """{normalised value of any of these fields: object} for the current school."""
    Model = apps.get_model(model)
    out = {}
    for o in Model.objects.all():
        for f in fields:
            v = getattr(o, f, '')
            if v:
                out.setdefault(norm(v), o)
    return out


@lookup('year')
def _year(ctx):
    return _by('education_academics.AcademicYear', 'name')


@ref_name('year')
def _year_name(o):
    return o.name


@lookup('class')
def _class(ctx):
    return _by('education_academics.SchoolClass', 'name')


@ref_name('class')
def _class_name(o):
    return o.name


@lookup('subject')
def _subject(ctx):
    out = _by('education_academics.Subject', 'name')
    for k, v in _by('education_academics.Subject', 'code').items():
        out.setdefault(k, v)
    return out


@ref_name('subject')
def _subject_name(o):
    return o.code or o.name


@lookup('teacher')
def _teacher(ctx):
    out = _by('education_academics.Teacher', 'employee_id')
    for k, v in _by('education_academics.Teacher', 'email').items():
        out.setdefault(k, v)
    return out


@ref_name('teacher')
def _teacher_name(o):
    return o.employee_id


@lookup('student')
def _student(ctx):
    return _by('education_students.Student', 'student_id')


@ref_name('student')
def _student_name(o):
    return o.student_id


@lookup('room')
def _room(ctx):
    return _by('education_academics.Classroom', 'code', 'name')


@ref_name('room')
def _room_name(o):
    return o.code


@lookup('invoice')
def _invoice(ctx):
    Invoice = apps.get_model('education_finance', 'Invoice')
    return {norm(i.invoice_number): i for i in Invoice.objects.all()}


@ref_name('invoice')
def _invoice_name(o):
    return o.invoice_number


@lookup('paygrade')
def _paygrade(ctx):
    return _by('education_hr.PayGrade', 'name')


@ref_name('paygrade')
def _paygrade_name(o):
    return o.name


def yes_no(v):
    return 'yes' if v else 'no'
