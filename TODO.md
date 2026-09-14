# Project To-Do List

## Pending Tasks

- [ ] **Cache Implementation for Product EAN Endpoint**
  - Implement caching mechanism for the endpoint querying products by EAN code to optimize response times and reduce database load.

- [ ] **Asynchronous Invoice Ingestion via Message Queue**
  - Refactor the Central Site invoice reception endpoint so that incoming invoice requests are published to a message queue instead of being directly inserted into the database.
  - Develop a dedicated consumer/worker process to process queued messages and perform the database insertions.
