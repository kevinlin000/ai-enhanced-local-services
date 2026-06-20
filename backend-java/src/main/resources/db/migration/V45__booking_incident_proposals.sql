ALTER TABLE tb_booking_incident
    ADD COLUMN proposal_status VARCHAR(20) NULL AFTER source,
    ADD COLUMN proposed_date DATE NULL AFTER proposal_status,
    ADD COLUMN proposed_time VARCHAR(10) NULL AFTER proposed_date,
    ADD COLUMN proposed_table_type VARCHAR(20) NULL AFTER proposed_time,
    ADD COLUMN proposed_people INT NULL AFTER proposed_table_type,
    ADD COLUMN proposal_message VARCHAR(500) NULL AFTER proposed_people,
    ADD COLUMN proposed_at DATETIME NULL AFTER proposal_message,
    ADD COLUMN proposal_accepted_at DATETIME NULL AFTER proposed_at,
    ADD INDEX idx_booking_incident_proposal_status (proposal_status, proposed_at);
