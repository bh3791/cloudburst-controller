CREATE TABLE job_status (
    job_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    ts TIMESTAMP,
    PRIMARY KEY (job_name)
);
