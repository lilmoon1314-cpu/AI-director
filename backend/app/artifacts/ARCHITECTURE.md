# Artifacts module

`router -> service -> repository/models` owns screenplay artifacts, stable blocks, immutable revision
snapshots, block-local diffs, directed dependencies, and stale marking. Cross-domain callers use only
`service.py`. The service may validate/touch ownership through `projects.service`; no other domain is
called. Project deletion calls `delete_project_data` from the projects router composition boundary.

