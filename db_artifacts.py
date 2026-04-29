from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexDefinition:
    table_name: str
    index_name: str
    ddl: str


@dataclass(frozen=True)
class CheckConstraintDefinition:
    table_name: str
    constraint_name: str
    ddl: str


@dataclass(frozen=True)
class ForeignKeyDefinition:
    table_name: str
    constraint_name: str
    column_name: str
    referenced_table: str
    referenced_column: str
    delete_rule: str = "RESTRICT"
    update_rule: str = "CASCADE"

    @property
    def ddl(self) -> str:
        return (
            f"ALTER TABLE `{self.table_name}` "
            f"ADD CONSTRAINT `{self.constraint_name}` "
            f"FOREIGN KEY (`{self.column_name}`) REFERENCES `{self.referenced_table}` (`{self.referenced_column}`) "
            f"ON DELETE {self.delete_rule} ON UPDATE {self.update_rule}"
        )


INDEX_DEFINITIONS = [
    IndexDefinition(
        table_name="users",
        index_name="idx_users_role_active",
        ddl="CREATE INDEX idx_users_role_active ON users (role, is_active)",
    ),
    IndexDefinition(
        table_name="categories",
        index_name="idx_categories_parent_name",
        ddl="CREATE INDEX idx_categories_parent_name ON categories (parent_id, name)",
    ),
    IndexDefinition(
        table_name="items",
        index_name="idx_items_status_close",
        ddl="CREATE INDEX idx_items_status_close ON items (status, close_time)",
    ),
    IndexDefinition(
        table_name="items",
        index_name="idx_items_category_status_close",
        ddl="CREATE INDEX idx_items_category_status_close ON items (category_id, status, close_time)",
    ),
    IndexDefinition(
        table_name="items",
        index_name="idx_items_seller_created",
        ddl="CREATE INDEX idx_items_seller_created ON items (seller_id, created_at)",
    ),
    IndexDefinition(
        table_name="items",
        index_name="ft_items_search",
        ddl=(
            "CREATE FULLTEXT INDEX ft_items_search "
            "ON items (title, brand, model_name, colorway, style_code, description)"
        ),
    ),
    IndexDefinition(
        table_name="bids",
        index_name="idx_bids_item_amount_time",
        ddl="CREATE INDEX idx_bids_item_amount_time ON bids (item_id, amount, placed_at, id)",
    ),
    IndexDefinition(
        table_name="bids",
        index_name="idx_bids_bidder_time",
        ddl="CREATE INDEX idx_bids_bidder_time ON bids (bidder_id, placed_at)",
    ),
    IndexDefinition(
        table_name="autobids",
        index_name="uq_autobids_item_bidder",
        ddl="CREATE UNIQUE INDEX uq_autobids_item_bidder ON autobids (item_id, bidder_id)",
    ),
    IndexDefinition(
        table_name="autobids",
        index_name="idx_autobids_item_limit",
        ddl="CREATE INDEX idx_autobids_item_limit ON autobids (item_id, upper_limit)",
    ),
    IndexDefinition(
        table_name="alerts",
        index_name="idx_alerts_user_category",
        ddl="CREATE INDEX idx_alerts_user_category ON alerts (user_id, category_id)",
    ),
    IndexDefinition(
        table_name="questions",
        index_name="idx_questions_item_created",
        ddl="CREATE INDEX idx_questions_item_created ON questions (item_id, created_at)",
    ),
    IndexDefinition(
        table_name="answers",
        index_name="idx_answers_question_created",
        ddl="CREATE INDEX idx_answers_question_created ON answers (question_id, created_at)",
    ),
    IndexDefinition(
        table_name="notifications",
        index_name="idx_notifications_user_read_time",
        ddl="CREATE INDEX idx_notifications_user_read_time ON notifications (user_id, is_read, created_at)",
    ),
]


CHECK_CONSTRAINT_DEFINITIONS = [
    CheckConstraintDefinition(
        table_name="items",
        constraint_name="ck_items_condition",
        ddl=(
            "ALTER TABLE `items` "
            "ADD CONSTRAINT `ck_items_condition` "
            "CHECK (`condition` IN ('new', 'used', 'like_new', 'good', 'fair'))"
        ),
    ),
]


FOREIGN_KEY_DEFINITIONS = [
    ForeignKeyDefinition("categories", "categories_ibfk_1", "parent_id", "categories", "id"),
    ForeignKeyDefinition("items", "items_ibfk_1", "seller_id", "users", "id"),
    ForeignKeyDefinition("items", "items_ibfk_2", "category_id", "categories", "id"),
    ForeignKeyDefinition("bids", "bids_ibfk_1", "item_id", "items", "id"),
    ForeignKeyDefinition("bids", "bids_ibfk_2", "bidder_id", "users", "id"),
    ForeignKeyDefinition("autobids", "autobids_ibfk_1", "item_id", "items", "id"),
    ForeignKeyDefinition("autobids", "autobids_ibfk_2", "bidder_id", "users", "id"),
    ForeignKeyDefinition("alerts", "alerts_ibfk_1", "user_id", "users", "id"),
    ForeignKeyDefinition("alerts", "alerts_ibfk_2", "category_id", "categories", "id"),
    ForeignKeyDefinition("notifications", "notifications_ibfk_1", "user_id", "users", "id"),
    ForeignKeyDefinition("questions", "questions_ibfk_1", "user_id", "users", "id"),
    ForeignKeyDefinition("questions", "questions_ibfk_2", "item_id", "items", "id"),
    ForeignKeyDefinition("answers", "answers_ibfk_1", "question_id", "questions", "id"),
    ForeignKeyDefinition("answers", "answers_ibfk_2", "rep_id", "users", "id"),
]


FUNCTION_DEFINITIONS = [
    (
        "fn_get_current_bid",
        """
        CREATE FUNCTION fn_get_current_bid(p_item_id INT)
        RETURNS FLOAT
        READS SQL DATA
        DETERMINISTIC
        BEGIN
            DECLARE v_result FLOAT;
            DECLARE v_start FLOAT;

            SELECT start_price
            INTO v_start
            FROM items
            WHERE id = p_item_id;

            SELECT COALESCE(MAX(amount), v_start)
            INTO v_result
            FROM bids
            WHERE item_id = p_item_id;

            RETURN v_result;
        END
        """,
    ),
]


VIEW_DEFINITIONS = [
    (
        "active_auction_summary",
        """
        CREATE VIEW active_auction_summary AS
        SELECT
            i.id AS item_id,
            i.title,
            i.category_id,
            i.seller_id,
            i.close_time,
            i.start_price,
            i.reserve_price,
            i.bid_increment,
            i.status
        FROM items AS i
        WHERE i.status = 'open'
        WITH CHECK OPTION
        """,
    ),
    (
        "closed_auction_sales",
        """
        CREATE VIEW closed_auction_sales AS
        SELECT
            i.id AS item_id,
            i.title,
            i.category_id,
            i.seller_id,
            winner.bidder_id AS buyer_id,
            winner.amount AS final_price,
            i.close_time
        FROM items AS i
        JOIN bids AS winner
            ON winner.id = (
                SELECT b2.id
                FROM bids AS b2
                WHERE b2.item_id = i.id
                ORDER BY b2.amount DESC, b2.placed_at ASC, b2.id ASC
                LIMIT 1
            )
        WHERE i.status = 'closed' AND winner.amount >= i.reserve_price
        """,
    ),
    (
        "user_auction_participation",
        """
        CREATE VIEW user_auction_participation AS
        SELECT
            u.id AS user_id,
            u.username,
            u.role,
            COALESCE(listed.listed_auctions, 0) AS listed_auctions,
            COALESCE(participation.bid_auctions, 0) AS bid_auctions,
            COALESCE(wins.win_count, 0) AS win_count,
            COALESCE(wins.total_spend, 0) AS total_spend
        FROM users AS u
        LEFT JOIN (
            SELECT seller_id, COUNT(*) AS listed_auctions
            FROM items
            GROUP BY seller_id
        ) AS listed
            ON listed.seller_id = u.id
        LEFT JOIN (
            SELECT bidder_id, COUNT(DISTINCT item_id) AS bid_auctions
            FROM bids
            GROUP BY bidder_id
        ) AS participation
            ON participation.bidder_id = u.id
        LEFT JOIN (
            SELECT buyer_id, COUNT(*) AS win_count, SUM(final_price) AS total_spend
            FROM closed_auction_sales
            GROUP BY buyer_id
        ) AS wins
            ON wins.buyer_id = u.id
        """,
    ),
    (
        "rep_moderation_queue",
        """
        CREATE VIEW rep_moderation_queue AS
        SELECT
            q.id AS question_id,
            q.body AS question_body,
            q.created_at AS asked_at,
            u.username AS asker,
            i.id AS item_id,
            i.title AS item_title,
            a.id AS answer_id,
            a.body AS answer_body
        FROM questions AS q
        JOIN users AS u ON u.id = q.user_id
        JOIN items AS i ON i.id = q.item_id
        LEFT JOIN answers AS a ON a.question_id = q.id
        ORDER BY q.created_at DESC
        """,
    ),
]


PROCEDURE_DEFINITIONS = [
    (
        "sp_recalculate_item_status",
        """
        CREATE PROCEDURE sp_recalculate_item_status(IN p_item_id INT)
        BEGIN
            DECLARE v_close_time DATETIME;
            DECLARE v_reserve_price DOUBLE;
            DECLARE v_status VARCHAR(20);
            DECLARE v_top_bid DOUBLE DEFAULT NULL;

            DECLARE EXIT HANDLER FOR SQLEXCEPTION
            BEGIN
                ROLLBACK;
                RESIGNAL;
            END;

            START TRANSACTION;

            SELECT close_time, reserve_price, status
            INTO v_close_time, v_reserve_price, v_status
            FROM items
            WHERE id = p_item_id
            FOR UPDATE;

            IF v_status <> 'removed' THEN
                SELECT amount
                INTO v_top_bid
                FROM bids
                WHERE item_id = p_item_id
                ORDER BY amount DESC, placed_at ASC, id ASC
                LIMIT 1;

                IF v_close_time > NOW() THEN
                    UPDATE items SET status = 'open' WHERE id = p_item_id;
                ELSEIF v_top_bid IS NULL OR v_top_bid < v_reserve_price THEN
                    UPDATE items SET status = 'no_winner' WHERE id = p_item_id;
                ELSE
                    UPDATE items SET status = 'closed' WHERE id = p_item_id;
                END IF;
            END IF;

            COMMIT;
        END
        """,
    ),
    (
        "sp_close_all_expired_auctions",
        """
        CREATE PROCEDURE sp_close_all_expired_auctions()
        BEGIN
            DECLARE done INT DEFAULT FALSE;
            DECLARE v_item_id INT;
            DECLARE expired_cursor CURSOR FOR
                SELECT id
                FROM items
                WHERE status = 'open' AND close_time <= NOW();
            DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

            OPEN expired_cursor;

            close_loop: LOOP
                FETCH expired_cursor INTO v_item_id;
                IF done THEN
                    LEAVE close_loop;
                END IF;

                CALL sp_recalculate_item_status(v_item_id);
            END LOOP;

            CLOSE expired_cursor;
        END
        """,
    ),
    (
        "sp_process_autobids",
        """
        CREATE PROCEDURE sp_process_autobids(
            IN p_item_id INT,
            IN p_last_bid_amount FLOAT,
            IN p_last_bidder_id INT
        )
        BEGIN
            DECLARE v_bid_increment FLOAT;
            DECLARE v_close_time DATETIME;
            DECLARE v_status VARCHAR(20);
            DECLARE v_current_bidder INT DEFAULT p_last_bidder_id;
            DECLARE v_current_amount FLOAT DEFAULT p_last_bid_amount;
            DECLARE v_counter_bidder INT DEFAULT NULL;
            DECLARE v_counter_limit FLOAT DEFAULT NULL;
            DECLARE v_new_amount FLOAT DEFAULT NULL;

            SELECT bid_increment, close_time, status
            INTO v_bid_increment, v_close_time, v_status
            FROM items
            WHERE id = p_item_id;

            IF v_status = 'open' AND v_close_time > NOW() THEN
                autobid_loop: LOOP
                    SET v_counter_bidder = NULL;
                    SET v_counter_limit = NULL;

                    SELECT bidder_id, upper_limit
                    INTO v_counter_bidder, v_counter_limit
                    FROM autobids
                    WHERE item_id = p_item_id
                      AND bidder_id <> v_current_bidder
                      AND upper_limit >= v_current_amount + v_bid_increment
                    ORDER BY upper_limit DESC, id ASC
                    LIMIT 1;

                    IF v_counter_bidder IS NULL THEN
                        LEAVE autobid_loop;
                    END IF;

                    SET v_new_amount = LEAST(v_counter_limit, v_current_amount + v_bid_increment);

                    IF v_new_amount IS NULL OR v_new_amount <= v_current_amount THEN
                        LEAVE autobid_loop;
                    END IF;

                    INSERT INTO bids (item_id, bidder_id, amount, placed_at, is_auto)
                    VALUES (p_item_id, v_counter_bidder, v_new_amount, NOW(), 1);

                    SET v_current_bidder = v_counter_bidder;
                    SET v_current_amount = v_new_amount;
                END LOOP;
            END IF;
        END
        """,
    ),
]


TRIGGER_DEFINITIONS = [
    (
        "trg_bids_before_insert_validate",
        """
        CREATE TRIGGER trg_bids_before_insert_validate
        BEFORE INSERT ON bids
        FOR EACH ROW
        BEGIN
            DECLARE v_status VARCHAR(20);
            DECLARE v_close_time DATETIME;
            DECLARE v_seller_id INT;
            DECLARE v_start_price DOUBLE;
            DECLARE v_bid_increment DOUBLE;
            DECLARE v_current_bid DOUBLE;

            SELECT status, close_time, seller_id, start_price, bid_increment
            INTO v_status, v_close_time, v_seller_id, v_start_price, v_bid_increment
            FROM items
            WHERE id = NEW.item_id
            FOR UPDATE;

            IF v_status <> 'open' OR v_close_time <= NOW() THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Cannot bid on a closed or expired auction.';
            END IF;

            IF NEW.bidder_id = v_seller_id THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Sellers cannot bid on their own auctions.';
            END IF;

            SELECT COALESCE(MAX(amount), v_start_price)
            INTO v_current_bid
            FROM bids
            WHERE item_id = NEW.item_id;

            IF NEW.amount < v_current_bid + v_bid_increment THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Bid amount does not meet the minimum increment.';
            END IF;

            IF NEW.placed_at IS NULL THEN
                SET NEW.placed_at = NOW();
            END IF;
        END
        """,
    ),
    (
        "trg_autobids_before_insert_validate",
        """
        CREATE TRIGGER trg_autobids_before_insert_validate
        BEFORE INSERT ON autobids
        FOR EACH ROW
        BEGIN
            DECLARE v_status VARCHAR(20);
            DECLARE v_close_time DATETIME;
            DECLARE v_seller_id INT;
            DECLARE v_start_price DOUBLE;
            DECLARE v_bid_increment DOUBLE;
            DECLARE v_current_bid DOUBLE DEFAULT NULL;
            DECLARE v_leader_id INT DEFAULT NULL;

            SELECT status, close_time, seller_id, start_price, bid_increment
            INTO v_status, v_close_time, v_seller_id, v_start_price, v_bid_increment
            FROM items
            WHERE id = NEW.item_id
            FOR UPDATE;

            IF v_status <> 'open' OR v_close_time <= NOW() THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Cannot set auto-bids on a closed or expired auction.';
            END IF;

            IF NEW.bidder_id = v_seller_id THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Sellers cannot place auto-bids on their own auctions.';
            END IF;

            SET v_current_bid = v_start_price;
            SET v_leader_id = NULL;

            SELECT bidder_id, amount
            INTO v_leader_id, v_current_bid
            FROM bids
            WHERE item_id = NEW.item_id
            ORDER BY amount DESC, placed_at ASC, id ASC
            LIMIT 1;

            IF v_leader_id = NEW.bidder_id THEN
                IF NEW.upper_limit < v_current_bid THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Auto-bid limit cannot be below the current leading bid.';
                END IF;
            ELSEIF NEW.upper_limit < v_current_bid + v_bid_increment THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Auto-bid limit does not meet the minimum increment.';
            END IF;
        END
        """,
    ),
]


EVENT_DEFINITIONS = [
    (
        "evt_close_expired_auctions",
        """
        CREATE EVENT IF NOT EXISTS evt_close_expired_auctions
        ON SCHEDULE EVERY 1 MINUTE
        STARTS CURRENT_TIMESTAMP
        DO CALL sp_close_all_expired_auctions()
        """,
    ),
]


def process_autobids_via_procedure(session, item_id: int, last_bid_amount: float, last_bidder_id: int) -> bool:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "mysql":
        return False

    connection = session.connection()
    cursor = connection.connection.cursor()
    try:
        cursor.callproc("sp_process_autobids", [item_id, last_bid_amount, last_bidder_id])
        while cursor.nextset():
            pass
    except Exception:
        return False
    finally:
        cursor.close()

    return True


def is_privilege_error(exc: Exception) -> bool:
    error_code = exc.args[0] if getattr(exc, "args", None) else None
    return error_code in {1227, 1419, 1449}


def install_named_database_object(
    *,
    cursor,
    object_kind: str,
    object_name: str,
    create_ddl: str,
    warnings: list[str],
    drop_sql: str | None = None,
    exists_query: str | None = None,
    exists_params: tuple | None = None,
) -> bool:
    exists = False

    if exists_query is not None:
        cursor.execute(exists_query, exists_params or ())
        exists = bool(cursor.fetchone()[0])

    if exists and drop_sql is not None:
        try:
            cursor.execute(drop_sql)
        except Exception as exc:
            if is_privilege_error(exc):
                warnings.append(
                    f"Could not replace MySQL {object_kind} {object_name}; keeping existing definition: {exc}"
                )
                return False
            raise

    try:
        cursor.execute(create_ddl)
        return True
    except Exception as exc:
        if is_privilege_error(exc):
            warnings.append(f"Could not create MySQL {object_kind} {object_name}: {exc}")
            return False
        raise


def ensure_check_constraints(cursor) -> int:
    applied_constraints = 0

    for constraint in CHECK_CONSTRAINT_DEFINITIONS:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.table_constraints
            WHERE constraint_schema = DATABASE()
              AND table_name = %s
              AND constraint_name = %s
              AND constraint_type = 'CHECK'
            """,
            (constraint.table_name, constraint.constraint_name),
        )
        if cursor.fetchone()[0]:
            continue

        cursor.execute(constraint.ddl)
        applied_constraints += 1

    return applied_constraints


def ensure_foreign_keys(cursor) -> int:
    applied_foreign_keys = 0

    for foreign_key in FOREIGN_KEY_DEFINITIONS:
        cursor.execute(
            """
            SELECT DISTINCT kcu.constraint_name
            FROM information_schema.key_column_usage AS kcu
            WHERE kcu.constraint_schema = DATABASE()
              AND kcu.table_name = %s
              AND kcu.column_name = %s
              AND kcu.referenced_table_name = %s
              AND kcu.referenced_column_name = %s
            """,
            (
                foreign_key.table_name,
                foreign_key.column_name,
                foreign_key.referenced_table,
                foreign_key.referenced_column,
            ),
        )
        matching_constraints = [row[0] for row in cursor.fetchall()]
        has_desired_definition = False

        for constraint_name in matching_constraints:
            cursor.execute(
                """
                SELECT delete_rule, update_rule
                FROM information_schema.referential_constraints
                WHERE constraint_schema = DATABASE()
                  AND table_name = %s
                  AND constraint_name = %s
                """,
                (foreign_key.table_name, constraint_name),
            )
            rule_row = cursor.fetchone()
            delete_rule = (rule_row[0] if rule_row else "").upper()
            update_rule = (rule_row[1] if rule_row else "").upper()

            if (
                constraint_name == foreign_key.constraint_name
                and delete_rule == foreign_key.delete_rule
                and update_rule == foreign_key.update_rule
            ):
                has_desired_definition = True
                continue

            cursor.execute(
                f"ALTER TABLE `{foreign_key.table_name}` DROP FOREIGN KEY `{constraint_name}`"
            )

        if has_desired_definition:
            continue

        cursor.execute(foreign_key.ddl)
        applied_foreign_keys += 1

    return applied_foreign_keys


def install_database_artifacts(engine) -> dict[str, int | bool | list[str] | str]:
    if engine.dialect.name != "mysql":
        return {
            "installed_indexes": 0,
            "installed_check_constraints": 0,
            "installed_foreign_keys": 0,
            "installed_views": 0,
            "installed_functions": 0,
            "installed_procedures": 0,
            "installed_triggers": 0,
            "installed_events": 0,
            "warnings": [],
            "autobid_strategy": "python_fallback",
            "skipped": True,
        }

    raw_connection = engine.raw_connection()
    cursor = raw_connection.cursor()
    created_indexes = 0
    applied_check_constraints = 0
    applied_foreign_keys = 0
    warnings: list[str] = []
    installed_events = 0
    installed_functions = 0
    installed_procedures = 0
    installed_views = 0
    installed_triggers = 0

    try:
        applied_check_constraints = ensure_check_constraints(cursor)
        applied_foreign_keys = ensure_foreign_keys(cursor)

        for index in INDEX_DEFINITIONS:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = %s
                  AND index_name = %s
                """,
                (index.table_name, index.index_name),
            )
            if cursor.fetchone()[0]:
                continue
            cursor.execute(index.ddl)
            created_indexes += 1

        for function_name, ddl in FUNCTION_DEFINITIONS:
            if install_named_database_object(
                cursor=cursor,
                object_kind="function",
                object_name=function_name,
                create_ddl=ddl,
                warnings=warnings,
                drop_sql=f"DROP FUNCTION IF EXISTS {function_name}",
                exists_query="""
                    SELECT COUNT(*)
                    FROM information_schema.routines
                    WHERE routine_schema = DATABASE()
                      AND routine_name = %s
                      AND routine_type = 'FUNCTION'
                """,
                exists_params=(function_name,),
            ):
                installed_functions += 1

        for procedure_name, ddl in PROCEDURE_DEFINITIONS:
            if install_named_database_object(
                cursor=cursor,
                object_kind="procedure",
                object_name=procedure_name,
                create_ddl=ddl,
                warnings=warnings,
                drop_sql=f"DROP PROCEDURE IF EXISTS {procedure_name}",
                exists_query="""
                    SELECT COUNT(*)
                    FROM information_schema.routines
                    WHERE routine_schema = DATABASE()
                      AND routine_name = %s
                      AND routine_type = 'PROCEDURE'
                """,
                exists_params=(procedure_name,),
            ):
                installed_procedures += 1

        for view_name, ddl in VIEW_DEFINITIONS:
            if install_named_database_object(
                cursor=cursor,
                object_kind="view",
                object_name=view_name,
                create_ddl=ddl,
                warnings=warnings,
                drop_sql=f"DROP VIEW IF EXISTS {view_name}",
                exists_query="""
                    SELECT COUNT(*)
                    FROM information_schema.views
                    WHERE table_schema = DATABASE()
                      AND table_name = %s
                """,
                exists_params=(view_name,),
            ):
                installed_views += 1

        for trigger_name, ddl in TRIGGER_DEFINITIONS:
            if install_named_database_object(
                cursor=cursor,
                object_kind="trigger",
                object_name=trigger_name,
                create_ddl=ddl,
                warnings=warnings,
                drop_sql=f"DROP TRIGGER IF EXISTS {trigger_name}",
                exists_query="""
                    SELECT COUNT(*)
                    FROM information_schema.triggers
                    WHERE trigger_schema = DATABASE()
                      AND trigger_name = %s
                """,
                exists_params=(trigger_name,),
            ):
                installed_triggers += 1

        try:
            cursor.execute("SET GLOBAL event_scheduler = ON")
        except Exception as exc:  # pragma: no cover - depends on local MySQL privileges
            warnings.append(f"Could not enable MySQL event scheduler globally: {exc}")

        for event_name, ddl in EVENT_DEFINITIONS:
            try:
                if install_named_database_object(
                    cursor=cursor,
                    object_kind="event",
                    object_name=event_name,
                    create_ddl=ddl,
                    warnings=warnings,
                    drop_sql=f"DROP EVENT IF EXISTS {event_name}",
                    exists_query="""
                        SELECT COUNT(*)
                        FROM information_schema.events
                        WHERE event_schema = DATABASE()
                          AND event_name = %s
                    """,
                    exists_params=(event_name,),
                ):
                    installed_events += 1
            except Exception as exc:  # pragma: no cover - depends on local MySQL privileges
                warnings.append(f"Could not create MySQL event {event_name}: {exc}")

        raw_connection.commit()
    finally:
        cursor.close()
        raw_connection.close()

    return {
        "installed_indexes": created_indexes,
        "installed_check_constraints": applied_check_constraints,
        "installed_foreign_keys": applied_foreign_keys,
        "installed_views": installed_views,
        "installed_functions": installed_functions,
        "installed_procedures": installed_procedures,
        "installed_triggers": installed_triggers,
        "installed_events": installed_events,
        "warnings": warnings,
        "autobid_strategy": "stored_procedure",
        "skipped": False,
    }
