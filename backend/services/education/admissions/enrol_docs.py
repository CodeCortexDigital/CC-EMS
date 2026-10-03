"""When an application becomes a student, the documents the family sent move onto the student's record."""
from django.core.files.base import ContentFile

CATEGORIES = (('birth', 'identity'), ('passport', 'identity'), ('id', 'identity'), ('report', 'report'), ('transcript', 'report'),
              ('medical', 'medical'), ('immuni', 'medical'), ('vaccin', 'medical'))


def category_for(doc_type: str) -> str:
    low = doc_type.lower()
    return next((cat for word, cat in CATEGORIES if word in low), 'other')


def copy_documents(application, student, user=None):
    """Copy each usable document (not one waiting to be sent again). Returns how many were copied."""
    from services.education.students.models import StudentDocument

    copied = 0
    for doc in application.documents.exclude(review_status='redo'):
        try:
            with doc.file.open('rb') as handle:
                content = ContentFile(handle.read())
        except (OSError, ValueError):
            continue  # the stored file is missing; the application keeps its record
        record = StudentDocument(student=student, tenant=student.tenant, title=doc.doc_type[:200], category=category_for(doc.doc_type),
                                 original_name=doc.original_name, size=doc.size, visible_to_family=True, from_family=True,
                                 uploaded_by=user if getattr(user, 'is_authenticated', False) else None)
        record.file.save(doc.original_name or f'{doc.doc_type}.bin', content, save=True)
        copied += 1
    return copied
