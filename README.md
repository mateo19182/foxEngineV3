# FoxEngineV3

## Todo

### Search

- show all fields in selector

### ETL

- new field to all uploads -> registered in
  - es el q se updatea con la api
- progress bar on server side upload
- internal server error resistant, stress test uploadss
- add zip support for uploads
  - compress files bigger than x Mb
- validate and clean file properly
- optimize import
  - on load big files web gets stuck
  - Bulk Writes and stream data with batches, disable index during insert
  - use compression, paralelize and MongoDB Write Concern
  - use polars for faster processing
  - is async better? motor
- breakdown results of import

### Schema/Db

- figure out if present in service, checked and hashed password
- try lots of records
- fuzzy search and/or regex
  - Anchoring your regex patterns
- duplicates on same record with one more or less field?
- update on same _id
- email // emails // email_address

### Checker

- api request
- add as tags instead of full values
- add file with only emails
- api endpoint for single
  - allow for rewind, if endpoint poisoned
  - db snapshots

### Other

- personalize export!!
- copy other cool stuff from v1 and v2!
- improve ui
  - shadcn
- optimize docker
  -  envs
- allow checker to check bd first
- add cluster to production
- llm integration xd

- document store
  https://github.com/minio/minio/blob/master/docs/select/README.md