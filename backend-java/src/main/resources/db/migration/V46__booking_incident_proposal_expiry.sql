ALTER TABLE tb_booking_incident
    ADD COLUMN proposal_expires_at DATETIME NULL AFTER proposed_at,
    ADD COLUMN proposal_declined_at DATETIME NULL AFTER proposal_accepted_at;
