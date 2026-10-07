import json
from pathlib import Path
import unittest

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(Path('contracts/kmj-autonomy-task.schema.json').read_text())
    def test_envelope(self):
        s = self.schema
        self.assertEqual(s['$schema'], 'https://json-schema.org/draft/2020-12/schema')
        self.assertEqual(s['title'], 'KMJ Autonomy Task')
        self.assertEqual(s['type'], 'object')
        self.assertFalse(s['additionalProperties'])
        self.assertEqual(set(s['required']), {'id', 'project', 'payload'})
        for name in ('id', 'project'):
            field = s['properties'][name]
            self.assertEqual(field['type'], 'string')
            self.assertEqual(field['minLength'], 1)
            self.assertEqual(field['maxLength'], 256)
            self.assertEqual(field['pattern'], r'\S')
    def test_private_default_and_bounded_kinds(self):
        p = self.schema['properties']['payload']
        self.assertEqual(p['type'], 'object')
        self.assertFalse(p['additionalProperties'])
        self.assertEqual(set(p['required']), {'kind', 'prompt'})
        self.assertEqual(set(p['properties']['kind']['enum']), {'plan','review','text','patch'})
        c = p['properties']['data_classification']
        self.assertEqual(set(c['enum']), {'public', 'confidential'})
        self.assertEqual(c['default'], 'confidential')
    def test_prompt_and_retry_bounds(self):
        fields = self.schema['properties']
        p = fields['payload']['properties']['prompt']
        self.assertEqual(p['type'], 'string')
        self.assertEqual(p['minLength'], 1)
        self.assertEqual(p['maxLength'], 65536)
        self.assertIn('byte', p['description'].lower())
        m = fields['max_attempts']
        self.assertEqual(m['type'], 'integer')
        self.assertEqual((m['minimum'], m['maximum'], m['default']), (1,10,3))
