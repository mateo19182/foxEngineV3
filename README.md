# FoxEngineV3

## Todo

- ingest script, accept zip, json and csv
  - add filename as source by default, allow change
  - don't do _id, mongodb should do it automatically
  - use a unique index to find dups (username + source ?)
- pagination
- JWT for auth
- figure out how to show record wih weird fields...
- history log with everything done
- copy other cool stuff from v1 and v2!
- try lots of records
- improve ui
- personlize export
- fuzzy search and/or regex
- add cluster to production
- llm integration xd

```python
python user_manager.py list
python user_manager.py add <username> <password>
python user_manager.py remove <username>
```
