"""Record project-board access without publishing profile or credentials."""
import json
from pathlib import Path
from publish import api, save

query = 'query { organization(login:"rayggxia-workspace") { projectsV2(first:10) { nodes { id number title url } } } }'
result = api('POST', '/graphql', {'query': query})
save('PROJECT_ACCESS.json', result)
print(json.dumps({'errors': result.get('errors'), 'data_available': bool(result.get('data'))}, ensure_ascii=False))
