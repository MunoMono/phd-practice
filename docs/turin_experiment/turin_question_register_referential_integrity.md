# Turin Question Register Referential Integrity

Research-question text is canonical in the Turin question register. Retrieval Plans persist a stable `question_id` reference rather than duplicating question text. Authorization validates referential integrity through that canonical ID.

For Q06, the researcher findings matrix and canonical register both contain the exact question text, and the immutable `CI2-v1` Retrieval Plan binds to it through `question_id = CI2`. The plan schema is intentionally not changed to duplicate question text.