from described_routes import ResourceTemplates

class Path(object):
    def __init__(self, parent, resource_template, params):
        self.parent = parent
        self.resource_template = resource_template
        self.params = params
        
        if parent:
            self.application = parent.application
        else:
            self.application = None
        
        if self.resource_template:
            self.uri = self.resource_template.uri_for(self.params, self.application.base)
        else:
            self.uri = None
            
    def with_params(self, *args, **kwargs):
        return type(self)(self, self.resource_template, self.make_child_params(None, args, kwargs))
        
    def make_child_params(self, resource_template, args, kwargs):
        child_params = dict(self.params)
        if args and isinstance(args[-1], dict):
            args = list(args)
            while args and isinstance(args[-1], dict):
                child_params.update(args.pop())
        if args and resource_template:
            child_params.update(dict(zip(resource_template.positional_params(self.resource_template), args)))
        child_params.update(kwargs)
        return child_params

    def child(self, rel, *args, **kwargs):
        for rt in self.candidate_child_templates(rel):
            child_params = self.make_child_params(rt, args, kwargs)
            if not [param for param in rt.params if param not in child_params]:
                return self.child_class_for(rt, child_params)(self, rt, child_params)
        else:
            raise LookupError(
                    "can't find child resource template of %s with rel %s and params %s" %
                    (repr(self), repr(rel), repr(child_params)))
                                
    def candidate_child_templates(self, rel):
        return self.resource_template.find_by_rel(rel)
        
    def child_class_for(self, resource_template, params):
        return self.application.child_class_for(resource_template, params)
                
    def __str__(self):
        return str(self.uri)

    def __getitem__(self, *args):
        if args and isinstance(args[0], tuple):
            args = args[0]
        return self.child(None, *args)
        
    def __getattr__(self, attr):
        if self.candidate_child_templates(attr):
            try:
                return self.child(attr)
            except LookupError:
                return lambda *args, **kwargs: self.child(attr, *args, **kwargs)
        else:
            raise AttributeError, attr

    def __call__(self, *args, **kwargs):
        return self.with_params(*args, **kwargs)
        

class Application(Path):
    def __init__(self, resource_templates, base=None, params={}):
        Path.__init__(self, None, None, params)
        if isinstance(resource_templates, ResourceTemplates):
            self.resource_templates = resource_templates
        else:
            self.resource_templates = ResourceTemplates(resource_templates)
        self.base = base
        self.application = self
        self.default_class = Path
        
    def candidate_child_templates(self, rel):
        return [self.resource_templates.all_by_name().get(rel)]

    def child_class_for(self, resource_template, params):
        return Path
        
    def uri(self):
        return self.base
        
    
if __name__ == "__main__":
    import unittest
    
    app = Application(
        [
            {
                'name':               'users',
                'uri_template':       'http://example.com/users{-prefix|.|format}',
                'optional_params':    ['format'],
                'options':            ['GET', 'POST'],
                'resource_templates': [
                    {
                        'name':               'new_user',
                        'rel':                'new',
                        'uri_template':       'http://example.com/users/new{-prefix|.|format}',
                        'optional_params':    ['format'],
                        'options':            ['GET'],
                    },
                    {
                        'name':               'user',
                        'uri_template':       'http://example.com/users/{user_id}{-prefix|.|format}',
                        'params':             ['user_id'],
                        'optional_params':    ['format'],
                        'options':            ['GET', 'PUT', 'DELETE'],
                        'resource_templates': [
                            {
                                'name':            'edit_user',
                                'rel':             'edit',
                                'uri_template':    'http://example.com/users/{user_id}/edit{-prefix|.|format}',
                                'params':          ['user_id'],
                                'optional_params': ['format'],
                                'options':         ['GET']
                            },
                            {
                                'name':            'user_articles',
                                'rel':             'articles',
                                'uri_template':    'http://example.com/users/{user_id}/articles{-prefix|.|format}',
                                'params':          ['user_id'],
                                'optional_params': ['format'],
                                'options':         ['GET', 'POST'],
                                'resource_templates': [
                                    {
                                        'name':               'user_article',
                                        'uri_template':       'http://example.com/users/{user_id}/articles/{article_id}{-prefix|.|format}',
                                        'params':             ['user_id', 'article_id'],
                                        'optional_params':    ['format'],
                                        'options':            ['GET', 'PUT', 'DELETE']
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'name':         'test_subresource_with_rel_and_mandatory_parameter',
                        'rel':          'foo',
                        'params':       ['bar'],
                        'uri_template': 'http://example.com/foo/{bar}'
                    }
                ]
            },
            {
                'name':          'test_with_no_uri_template',
                'path_template': '/path'
            }
        ],
        base="http://example.com/base")


    class TestApplication(unittest.TestCase):        
        def test_child(self):
            self.assertEqual('http://example.com/users',           app.child('users').uri)
            self.assertEqual('http://example.com/users.json',      app.child('users', format='json').uri)
            self.assertEqual('http://example.com/users.json',      app.child('users', {'format': 'json'}).uri)
            self.assertEqual('http://example.com/users.json',      app.child('users', 'json').uri)
            
        def test_child_via_getattr(self):
            self.assertEqual('http://example.com/users',           app.users.uri)
        
        def test_child_with_mandatory_params(self):
            self.assertEqual(type(lambda : None), type(app.user))
            self.assertRaises(LookupError, lambda:app.user())
            self.assertEqual('http://example.com/users/dojo',      app.user(user_id='dojo').uri)
            self.assertEqual('http://example.com/users/dojo',      app.user('dojo').uri)
            
        def test_child_with_multiple_params(self):
            self.assertEqual("http://example.com/users/dojo/articles/foo.json", app.user_article('dojo', 'foo', format='json').uri)

        def test_child_callable(self):
            self.assertEqual('http://example.com/users',           app.users().uri)
            self.assertEqual('http://example.com/users.json',      app.users(format='json').uri)
            self.assertEqual('http://example.com/users.json',      app.users({'format': 'json'}).uri)


    class TestPath(unittest.TestCase):
        def test_child(self):
            self.assertEqual('http://example.com/users/dojo',      app.users.child(None, 'dojo').uri)
            self.assertEqual('http://example.com/users/dojo.json', app.users.child(None, 'dojo', format='json').uri)
            self.assertEqual('http://example.com/users/dojo.json', app.users.child(None, {'user_id': 'dojo', 'format': 'json'}).uri)

        def test_child_via_getattr(self):
            self.assertEqual('http://example.com/users/new',       app.users.new.uri)

        def test_child_with_mandatory_params(self):
            self.assertEqual(type(lambda : None), type(app.users.foo))
            self.assertRaises(LookupError, lambda:app.users.foo())
            self.assertEqual('http://example.com/foo/baz',         app.users.foo('baz').uri)

        def test_child_callable(self):
            self.assertEqual('http://example.com/users/new',       app.users.new().uri)
            self.assertEqual('http://example.com/users/new.json',  app.users.new(format='json').uri)
            self.assertEqual('http://example.com/users/new.json',  app.users.new({'format': 'json'}).uri)
            
        def test_index(self):
            self.assertEqual('http://example.com/users/dojo',      app.users['dojo'].uri)
            self.assertEqual('http://example.com/users/dojo.json', app.users['dojo', {'format': 'json'}].uri)
            
        def test_uri_with_no_uri_template(self):
            self.assertEqual('http://example.com/base/path',       app.test_with_no_uri_template.uri)
            

    unittest.main()
