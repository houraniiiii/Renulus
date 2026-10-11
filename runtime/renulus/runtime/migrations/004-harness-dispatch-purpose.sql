-- SPDX-License-Identifier: MIT
-- Historical attempts remain nullable until their purpose can be identified.
ALTER TABLE harness_configuration_attempts ADD COLUMN dispatch_purpose TEXT;
