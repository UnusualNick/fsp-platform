import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from service import ApiError, Service
from storage import SCHEMA, Storage


class OrganizerRequirementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Storage(Path(self.tmp.name) / 'test.sqlite')
        self.service = Service(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def register(self, role='candidate'):
        data = {'email': f'{role}@example.test', 'password': 'LongPassword42!', 'role': role, 'consent': True}
        response = self.service.register(data)
        self.service.verify({'token': response['verification_token']})
        _, token = self.service.login(data)
        return self.service.auth(token)

    def test_resume_fields_do_not_change_grade_or_reveal_contacts(self):
        candidate = self.register()
        employer = self.register('employer')
        data = {'name': 'Тестовый кандидат', 'roles': 'Backend', 'experience': '3 года',
                'soft_skills': 'Код-ревью и наставничество', 'contact': '@private', 'skills': 'Python',
                'published': True, 'grade': 'Senior'}
        profile = self.service.update_profile(candidate, data)['profile']
        self.assertIsNone(profile['grade'])
        self.assertEqual('3 года', profile['experience'])
        self.assertEqual([], self.service.candidates(employer, {})['candidates'])
        with self.store.connect() as db:
            db.execute("UPDATE profiles SET grade='Middle',score=90 WHERE user_id=?", (candidate['id'],))
        row = self.service.candidates(employer, {})['candidates'][0]
        for key in ('roles', 'experience', 'soft_skills'):
            self.assertEqual(data[key], row[key])
        for key in ('email', 'contact', 'password'):
            self.assertNotIn(key, row)
        self.assertEqual('Middle', row['grade'])

    def test_profile_rejects_non_text_resume_fields(self):
        candidate = self.register()
        for key, value in [('roles', []), ('experience', 8), ('soft_skills', 'x' * 2001)]:
            with self.subTest(key=key), self.assertRaises(ApiError) as error:
                self.service.update_profile(candidate, {'name': 'Имя', key: value})
            self.assertEqual(400, error.exception.status)

    def test_company_activity_survives_restart(self):
        employer = self.register('employer')
        data = {'name': 'Компания', 'contact': 'hr@example.test', 'activity': 'Разработка ПО',
                'description': 'Команда инфраструктуры'}
        self.service.update_profile(employer, data)
        reopened = Service(Storage(self.store.path)).me(employer)['profile']
        self.assertEqual(data['activity'], reopened['activity'])
        self.assertEqual(data['description'], reopened['description'])

    def test_survey_history_keeps_each_original_industry(self):
        candidate = self.register()
        self.service.update_profile(candidate, {'name': 'Имя'})
        for industry in ('Финтех', 'Образование'):
            attempt = self.service.start_assessment(candidate, {
                'industry': industry, 'specialization': 'backend', 'grade': 'Junior'})
            self.assertEqual(industry, attempt['industry'])
            with self.store.connect() as db:
                form = json.loads(db.execute('SELECT form FROM attempts WHERE id=?',
                                             (attempt['attempt_id'],)).fetchone()[0])
            answers = {q['id']: (q['answer'] + 1) % 4 for q in form['questions']}
            result = self.service.submit_assessment(candidate, {'attempt_id': attempt['attempt_id'], 'answers': answers})
            self.assertFalse(result['passed'])
        history = self.service.me(candidate)['history']
        self.assertEqual(['Образование', 'Финтех'], [h['result']['industry'] for h in history])

    def test_migration_preserves_legacy_records_and_is_repeatable(self):
        path = Path(self.tmp.name) / 'legacy.sqlite'
        with sqlite3.connect(path) as db:
            db.executescript(SCHEMA)
            db.execute("INSERT INTO users VALUES(7,'saved@test.ru','hash','candidate',1,1,1)")
            db.execute("INSERT INTO profiles(user_id,name,contact,grade,score) VALUES(7,'Сохранён','@old','Middle',88)")
        for _ in range(2):
            with Storage(path).connect() as db:
                row = dict(db.execute('SELECT * FROM profiles WHERE user_id=7').fetchone())
                self.assertEqual(('Сохранён', '@old', 'Middle', 88),
                                 tuple(row[k] for k in ('name', 'contact', 'grade', 'score')))
                self.assertEqual(['', '', ''], [row[k] for k in ('roles', 'experience', 'soft_skills')])

    def test_production_verification_does_not_return_token(self):
        service = Service(self.store, demo=False)
        with patch.dict(os.environ, {'SMTP_HOST': 'mail.test', 'SMTP_FROM': 'noreply@test.ru',
                                    'PUBLIC_URL': 'https://fsp.test'}), patch('service.smtplib.SMTP') as smtp:
            response = service.register({'email': 'mail@test.ru', 'password': 'LongPassword42!',
                                         'role': 'candidate', 'consent': True})
        self.assertNotIn('verification_token', response)
        smtp.return_value.__enter__.return_value.starttls.assert_called_once()
        message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        token = message.get_content().split('?verify=')[1].strip()
        service.verify({'token': token})
        with self.store.connect() as db:
            self.assertEqual(1, db.execute('SELECT verified FROM users').fetchone()[0])

    def test_production_email_failure_rolls_back_registration(self):
        service = Service(self.store, demo=False)
        with patch.object(service, 'send_verification', side_effect=ApiError(503, 'mail unavailable')):
            with self.assertRaises(ApiError):
                service.register({'email': 'mail@test.ru', 'password': 'LongPassword42!',
                                  'role': 'candidate', 'consent': True})
        with self.store.connect() as db:
            self.assertEqual(0, db.execute('SELECT COUNT(*) FROM users').fetchone()[0])
            self.assertEqual(0, db.execute('SELECT COUNT(*) FROM verifications').fetchone()[0])

    def test_openapi_has_unique_parameters_and_json_contracts(self):
        spec = json.loads((Path(__file__).parents[1] / 'docs/openapi.json').read_text())
        for path, methods in spec['paths'].items():
            for method, operation in methods.items():
                with self.subTest(path=path, method=method):
                    keys = [(p['in'], p['name']) for p in operation.get('parameters', [])]
                    self.assertEqual(len(keys), len(set(keys)))
                    if path != '/api/profile.pdf':
                        self.assertIn('schema', operation['responses']['200']['content']['application/json'])
                    if method in ('post', 'put') and path != '/api/auth/logout':
                        self.assertIn('schema', operation['requestBody']['content']['application/json'])
