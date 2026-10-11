"""Metric-based wrapping for a candidate's complete, private PDF resume."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from assessment import SPECIALIZATIONS


def profile_sections(me):
    profile = me['profile']
    return [
        ('Отрасль', profile['industry']),
        ('Специализация', SPECIALIZATIONS.get(profile['specialization'], '')),
        ('Грейд', profile['grade'] or 'Категория ещё не подтверждена'),
        ('Результат теста', f'{profile["score"]}%'),
        ('Стек', profile['skills']),
        ('Роли', profile.get('roles', '')),
        ('Стаж и опыт', profile.get('experience', '')),
        ('Работа в команде', profile.get('soft_skills', '')),
        ('О себе', profile['about']),
        ('Email', me['user']['email']),
        ('Контакт', profile['contact']),
    ]


def build_profile_pdf(me):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    font = Path(__file__).parent / 'web/fonts/DejaVuSans.ttf'
    if 'ProfileFont' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ProfileFont', str(font)))
    body = ParagraphStyle('body', fontName='ProfileFont', fontSize=11, leading=17, spaceAfter=9)
    title = ParagraphStyle('title', parent=body, fontSize=19, leading=25, spaceAfter=16)

    def paragraph(value, style=body):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), style)

    profile = me['profile']
    content = [paragraph('ФСП / Профиль кандидата', title), paragraph(profile['name'], title)]
    content += [paragraph(f'{label}: {value or "Не указано"}') for label, value in profile_sections(me)]
    content.extend([Spacer(1, 10), paragraph('Достижения ФСП', title)])
    content += [paragraph(f'{a["event"]}, место {a["place"]}') for a in profile['achievements']]
    if not profile['achievements']:
        content.append(paragraph('Достижений ФСП нет. Для подбора они необязательны'))
    content.append(paragraph('Членство в ФСП не учитывается в подборе'))
    if me.get('demo'):
        content.append(paragraph('Учебный профиль. Данные реестра ФСП воспроизведены для демонстрации'))
    buffer = BytesIO()
    SimpleDocTemplate(buffer, leftMargin=42, rightMargin=42, topMargin=42, bottomMargin=42).build(content)
    return buffer.getvalue()
