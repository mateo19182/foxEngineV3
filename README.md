# FoxEngineV3

## Todo

### ETL

take file out when upload completed..

- internal server error resistant...
- add zip support
- validate and clean file properly
  - don't do _id, mongodb does it automatically, replace on same id or exactly same values
- Bulk Writes and stream data with batches, disable index during insert
- use compression, paralelize and MongoDB Write Concern
- use polars for faster processing
- ingest script
- breakdown better results of import
- is async better? motor
- add separator chooser back?

### Schema/Db

- figure out if present in service, checked and hashed password 
- figure out how to show record new fields
- try lots of records
- fuzzy search and/or regex
  - Anchoring your regex patterns


### Other

- copy other cool stuff from v1 and v2!
- improve ui
  - shadcn
- optimize docker
- personlize export
- pagination, handlebars?
- allow checker to check bd first
- add cluster to production
- llm integration xd

- document store
  https://github.com/minio/minio/blob/master/docs/select/README.md