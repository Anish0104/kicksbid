-- KicksBid canonical MySQL schema
-- This file documents the tables, views, functions, procedures, triggers, and event
-- installed by seed.py through db_artifacts.py.

SET FOREIGN_KEY_CHECKS = 0;

DROP VIEW IF EXISTS `rep_moderation_queue`;
DROP VIEW IF EXISTS `user_auction_participation`;
DROP VIEW IF EXISTS `closed_auction_sales`;
DROP VIEW IF EXISTS `active_auction_summary`;

DROP EVENT IF EXISTS `evt_close_expired_auctions`;

DROP TRIGGER IF EXISTS `trg_autobids_before_insert_validate`;
DROP TRIGGER IF EXISTS `trg_bids_before_insert_validate`;

DROP PROCEDURE IF EXISTS `sp_process_autobids`;
DROP PROCEDURE IF EXISTS `sp_close_all_expired_auctions`;
DROP PROCEDURE IF EXISTS `sp_recalculate_item_status`;

DROP FUNCTION IF EXISTS `fn_get_current_bid`;

DROP TABLE IF EXISTS `answers`;
DROP TABLE IF EXISTS `questions`;
DROP TABLE IF EXISTS `notifications`;
DROP TABLE IF EXISTS `alerts`;
DROP TABLE IF EXISTS `autobids`;
DROP TABLE IF EXISTS `bids`;
DROP TABLE IF EXISTS `items`;
DROP TABLE IF EXISTS `categories`;
DROP TABLE IF EXISTS `users`;
fn_get_current_bidkeywordscategory_idcategory_iduser_id
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(80) NOT NULL,
  `email` varchar(120) NOT NULL,
  `password_hash` varchar(256) NOT NULL,
  `role` varchar(20) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  KEY `idx_users_role_active` (`role`, `is_active`),
  CONSTRAINT `ck_users_role` CHECK (`role` IN ('user', 'rep', 'admin', 'deleted'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `categories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `parent_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_categories_parent_name` (`parent_id`, `name`),
  CONSTRAINT `categories_ibfk_1`
    FOREIGN KEY (`parent_id`) REFERENCES `categories` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `brand` varchar(100) NOT NULL,
  `model_name` varchar(100) NOT NULL,
  `colorway` varchar(100) NOT NULL,
  `style_code` varchar(50) NOT NULL,
  `us_size` float NOT NULL,
  `condition` varchar(10) NOT NULL,
  `box_included` tinyint(1) NOT NULL,
  `description` text NOT NULL,
  `seller_id` int NOT NULL,
  `category_id` int NOT NULL,
  `start_price` float NOT NULL,
  `reserve_price` float NOT NULL,
  `bid_increment` float NOT NULL,
  `image_url_override` text DEFAULT NULL,
  `image_data` longblob DEFAULT NULL,
  `close_time` datetime NOT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `seller_id` (`seller_id`),
  KEY `category_id` (`category_id`),
  KEY `idx_items_status_close` (`status`, `close_time`),
  KEY `idx_items_category_status_close` (`category_id`, `status`, `close_time`),
  KEY `idx_items_seller_created` (`seller_id`, `created_at`),
  FULLTEXT KEY `ft_items_search` (`title`, `brand`, `model_name`, `colorway`, `style_code`, `description`),
  CONSTRAINT `items_ibfk_1`
    FOREIGN KEY (`seller_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `items_ibfk_2`
    FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `ck_items_start_price` CHECK (`start_price` > 0),
  CONSTRAINT `ck_items_reserve_price` CHECK (`reserve_price` >= 0),
  CONSTRAINT `ck_items_bid_increment` CHECK (`bid_increment` > 0),
  CONSTRAINT `ck_items_us_size` CHECK (`us_size` > 0),
  CONSTRAINT `ck_items_condition` CHECK (`condition` IN ('new', 'used', 'like_new', 'good', 'fair')),
  CONSTRAINT `ck_items_status` CHECK (`status` IN ('open', 'closed', 'no_winner', 'removed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `bids` (
  `id` int NOT NULL AUTO_INCREMENT,
  `item_id` int NOT NULL,
  `bidder_id` int NOT NULL,
  `amount` float NOT NULL,
  `placed_at` datetime NOT NULL,
  `is_auto` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `item_id` (`item_id`),
  KEY `bidder_id` (`bidder_id`),
  KEY `idx_bids_item_amount_time` (`item_id`, `amount`, `placed_at`, `id`),
  KEY `idx_bids_bidder_time` (`bidder_id`, `placed_at`),
  CONSTRAINT `bids_ibfk_1`
    FOREIGN KEY (`item_id`) REFERENCES `items` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `bids_ibfk_2`
    FOREIGN KEY (`bidder_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `ck_bids_amount` CHECK (`amount` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `autobids` (
  `id` int NOT NULL AUTO_INCREMENT,
  `item_id` int NOT NULL,
  `bidder_id` int NOT NULL,
  `upper_limit` float NOT NULL,
  PRIMARY KEY (`id`),
  KEY `item_id` (`item_id`),
  KEY `bidder_id` (`bidder_id`),
  KEY `idx_autobids_item_limit` (`item_id`, `upper_limit`),
  UNIQUE KEY `uq_autobids_item_bidder` (`item_id`, `bidder_id`),
  CONSTRAINT `autobids_ibfk_1`
    FOREIGN KEY (`item_id`) REFERENCES `items` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `autobids_ibfk_2`
    FOREIGN KEY (`bidder_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `ck_autobids_upper_limit` CHECK (`upper_limit` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `alerts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `category_id` int NOT NULL,
  `keywords` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `category_id` (`category_id`),
  KEY `idx_alerts_user_category` (`user_id`, `category_id`),
  CONSTRAINT `alerts_ibfk_1`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `alerts_ibfk_2`
    FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `notifications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `message` varchar(500) NOT NULL,
  `is_read` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `idx_notifications_user_read_time` (`user_id`, `is_read`, `created_at`),
  CONSTRAINT `notifications_ibfk_1`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `questions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `item_id` int NOT NULL,
  `body` text NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `item_id` (`item_id`),
  KEY `idx_questions_item_created` (`item_id`, `created_at`),
  CONSTRAINT `questions_ibfk_1`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `questions_ibfk_2`
    FOREIGN KEY (`item_id`) REFERENCES `items` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `answers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `question_id` int NOT NULL,
  `rep_id` int NOT NULL,
  `body` text NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `question_id` (`question_id`),
  KEY `rep_id` (`rep_id`),
  KEY `idx_answers_question_created` (`question_id`, `created_at`),
  CONSTRAINT `answers_ibfk_1`
    FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `answers_ibfk_2`
    FOREIGN KEY (`rep_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DELIMITER //

CREATE FUNCTION `fn_get_current_bid`(`p_item_id` INT)
RETURNS FLOAT
READS SQL DATA
DETERMINISTIC
BEGIN
  DECLARE `v_result` FLOAT;
  DECLARE `v_start` FLOAT;

  SELECT `start_price`
  INTO `v_start`
  FROM `items`
  WHERE `id` = `p_item_id`;

  SELECT COALESCE(MAX(`amount`), `v_start`)
  INTO `v_result`
  FROM `bids`
  WHERE `item_id` = `p_item_id`;

  RETURN `v_result`;
END//

CREATE PROCEDURE `sp_recalculate_item_status`(IN `p_item_id` INT)
BEGIN
  DECLARE `v_close_time` DATETIME;
  DECLARE `v_reserve_price` DOUBLE;
  DECLARE `v_status` VARCHAR(20);
  DECLARE `v_top_bid` DOUBLE DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;

  SELECT `close_time`, `reserve_price`, `status`
  INTO `v_close_time`, `v_reserve_price`, `v_status`
  FROM `items`
  WHERE `id` = `p_item_id`
  FOR UPDATE;

  IF `v_status` <> 'removed' THEN
    SELECT `amount`
    INTO `v_top_bid`
    FROM `bids`
    WHERE `item_id` = `p_item_id`
    ORDER BY `amount` DESC, `placed_at` ASC, `id` ASC
    LIMIT 1;

    IF `v_close_time` > NOW() THEN
      UPDATE `items` SET `status` = 'open' WHERE `id` = `p_item_id`;
    ELSEIF `v_top_bid` IS NULL OR `v_top_bid` < `v_reserve_price` THEN
      UPDATE `items` SET `status` = 'no_winner' WHERE `id` = `p_item_id`;
    ELSE
      UPDATE `items` SET `status` = 'closed' WHERE `id` = `p_item_id`;
    END IF;
  END IF;

  COMMIT;
END//

CREATE PROCEDURE `sp_close_all_expired_auctions`()
BEGIN
  DECLARE `done` INT DEFAULT FALSE;
  DECLARE `v_item_id` INT;
  DECLARE `expired_cursor` CURSOR FOR
    SELECT `id`
    FROM `items`
    WHERE `status` = 'open' AND `close_time` <= NOW();
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET `done` = TRUE;

  OPEN `expired_cursor`;

  close_loop: LOOP
    FETCH `expired_cursor` INTO `v_item_id`;
    IF `done` THEN
      LEAVE close_loop;
    END IF;

    CALL `sp_recalculate_item_status`(`v_item_id`);
  END LOOP;

  CLOSE `expired_cursor`;
END//

CREATE PROCEDURE `sp_process_autobids`(
  IN `p_item_id` INT,
  IN `p_last_bid_amount` FLOAT,
  IN `p_last_bidder_id` INT
)
BEGIN
  DECLARE `v_bid_increment` FLOAT;
  DECLARE `v_close_time` DATETIME;
  DECLARE `v_status` VARCHAR(20);
  DECLARE `v_current_bidder` INT DEFAULT `p_last_bidder_id`;
  DECLARE `v_current_amount` FLOAT DEFAULT `p_last_bid_amount`;
  DECLARE `v_counter_bidder` INT DEFAULT NULL;
  DECLARE `v_counter_limit` FLOAT DEFAULT NULL;
  DECLARE `v_new_amount` FLOAT DEFAULT NULL;

  SELECT `bid_increment`, `close_time`, `status`
  INTO `v_bid_increment`, `v_close_time`, `v_status`
  FROM `items`
  WHERE `id` = `p_item_id`;

  IF `v_status` = 'open' AND `v_close_time` > NOW() THEN
    autobid_loop: LOOP
      SET `v_counter_bidder` = NULL;
      SET `v_counter_limit` = NULL;

      SELECT `bidder_id`, `upper_limit`
      INTO `v_counter_bidder`, `v_counter_limit`
      FROM `autobids`
      WHERE `item_id` = `p_item_id`
        AND `bidder_id` <> `v_current_bidder`
        AND `upper_limit` >= `v_current_amount` + `v_bid_increment`
      ORDER BY `upper_limit` DESC, `id` ASC
      LIMIT 1;

      IF `v_counter_bidder` IS NULL THEN
        LEAVE autobid_loop;
      END IF;

      SET `v_new_amount` = LEAST(`v_counter_limit`, `v_current_amount` + `v_bid_increment`);

      IF `v_new_amount` IS NULL OR `v_new_amount` <= `v_current_amount` THEN
        LEAVE autobid_loop;
      END IF;

      INSERT INTO `bids` (`item_id`, `bidder_id`, `amount`, `placed_at`, `is_auto`)
      VALUES (`p_item_id`, `v_counter_bidder`, `v_new_amount`, NOW(), 1);

      SET `v_current_bidder` = `v_counter_bidder`;
      SET `v_current_amount` = `v_new_amount`;
    END LOOP;
  END IF;
END//

CREATE TRIGGER `trg_bids_before_insert_validate`
BEFORE INSERT ON `bids`
FOR EACH ROW
BEGIN
  DECLARE `v_status` VARCHAR(20);
  DECLARE `v_close_time` DATETIME;
  DECLARE `v_seller_id` INT;
  DECLARE `v_start_price` DOUBLE;
  DECLARE `v_bid_increment` DOUBLE;
  DECLARE `v_current_bid` DOUBLE;

  SELECT `status`, `close_time`, `seller_id`, `start_price`, `bid_increment`
  INTO `v_status`, `v_close_time`, `v_seller_id`, `v_start_price`, `v_bid_increment`
  FROM `items`
  WHERE `id` = NEW.`item_id`
  FOR UPDATE;

  IF `v_status` <> 'open' OR `v_close_time` <= NOW() THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Cannot bid on a closed or expired auction.';
  END IF;

  IF NEW.`bidder_id` = `v_seller_id` THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Sellers cannot bid on their own auctions.';
  END IF;

  SELECT COALESCE(MAX(`amount`), `v_start_price`)
  INTO `v_current_bid`
  FROM `bids`
  WHERE `item_id` = NEW.`item_id`;

  IF NEW.`amount` < `v_current_bid` + `v_bid_increment` THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Bid amount does not meet the minimum increment.';
  END IF;

  IF NEW.`placed_at` IS NULL THEN
    SET NEW.`placed_at` = NOW();
  END IF;
END//

CREATE TRIGGER `trg_autobids_before_insert_validate`
BEFORE INSERT ON `autobids`
FOR EACH ROW
BEGIN
  DECLARE `v_status` VARCHAR(20);
  DECLARE `v_close_time` DATETIME;
  DECLARE `v_seller_id` INT;
  DECLARE `v_start_price` DOUBLE;
  DECLARE `v_bid_increment` DOUBLE;
  DECLARE `v_current_bid` DOUBLE DEFAULT NULL;
  DECLARE `v_leader_id` INT DEFAULT NULL;

  SELECT `status`, `close_time`, `seller_id`, `start_price`, `bid_increment`
  INTO `v_status`, `v_close_time`, `v_seller_id`, `v_start_price`, `v_bid_increment`
  FROM `items`
  WHERE `id` = NEW.`item_id`
  FOR UPDATE;

  IF `v_status` <> 'open' OR `v_close_time` <= NOW() THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Cannot set auto-bids on a closed or expired auction.';
  END IF;

  IF NEW.`bidder_id` = `v_seller_id` THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Sellers cannot place auto-bids on their own auctions.';
  END IF;

  SET `v_current_bid` = `v_start_price`;
  SET `v_leader_id` = NULL;

  SELECT `bidder_id`, `amount`
  INTO `v_leader_id`, `v_current_bid`
  FROM `bids`
  WHERE `item_id` = NEW.`item_id`
  ORDER BY `amount` DESC, `placed_at` ASC, `id` ASC
  LIMIT 1;

  IF `v_leader_id` = NEW.`bidder_id` THEN
    IF NEW.`upper_limit` < `v_current_bid` THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Auto-bid limit cannot be below the current leading bid.';
    END IF;
  ELSEIF NEW.`upper_limit` < `v_current_bid` + `v_bid_increment` THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Auto-bid limit does not meet the minimum increment.';
  END IF;
END//

DELIMITER ;

CREATE VIEW `active_auction_summary` AS
SELECT
  `i`.`id` AS `item_id`,
  `i`.`title` AS `title`,
  `i`.`category_id` AS `category_id`,
  `i`.`seller_id` AS `seller_id`,
  `i`.`close_time` AS `close_time`,
  `i`.`start_price` AS `start_price`,
  `i`.`reserve_price` AS `reserve_price`,
  `i`.`bid_increment` AS `bid_increment`,
  `i`.`status` AS `status`
FROM `items` AS `i`
WHERE `i`.`status` = 'open'
WITH CHECK OPTION;

CREATE VIEW `closed_auction_sales` AS
SELECT
  `i`.`id` AS `item_id`,
  `i`.`title` AS `title`,
  `i`.`category_id` AS `category_id`,
  `i`.`seller_id` AS `seller_id`,
  `winner`.`bidder_id` AS `buyer_id`,
  `winner`.`amount` AS `final_price`,
  `i`.`close_time` AS `close_time`
FROM `items` AS `i`
JOIN `bids` AS `winner`
  ON `winner`.`id` = (
    SELECT `b2`.`id`
    FROM `bids` AS `b2`
    WHERE `b2`.`item_id` = `i`.`id`
    ORDER BY `b2`.`amount` DESC, `b2`.`placed_at` ASC, `b2`.`id` ASC
    LIMIT 1
  )
WHERE `i`.`status` = 'closed' AND `winner`.`amount` >= `i`.`reserve_price`;

CREATE VIEW `user_auction_participation` AS
SELECT
  `u`.`id` AS `user_id`,
  `u`.`username` AS `username`,
  `u`.`role` AS `role`,
  COALESCE(`listed`.`listed_auctions`, 0) AS `listed_auctions`,
  COALESCE(`participation`.`bid_auctions`, 0) AS `bid_auctions`,
  COALESCE(`wins`.`win_count`, 0) AS `win_count`,
  COALESCE(`wins`.`total_spend`, 0) AS `total_spend`
FROM `users` AS `u`
LEFT JOIN (
  SELECT `seller_id`, COUNT(*) AS `listed_auctions`
  FROM `items`
  GROUP BY `seller_id`
) AS `listed`
  ON `listed`.`seller_id` = `u`.`id`
LEFT JOIN (
  SELECT `bidder_id`, COUNT(DISTINCT `item_id`) AS `bid_auctions`
  FROM `bids`
  GROUP BY `bidder_id`
) AS `participation`
  ON `participation`.`bidder_id` = `u`.`id`
LEFT JOIN (
  SELECT `buyer_id`, COUNT(*) AS `win_count`, SUM(`final_price`) AS `total_spend`
  FROM `closed_auction_sales`
  GROUP BY `buyer_id`
) AS `wins`
  ON `wins`.`buyer_id` = `u`.`id`;

CREATE VIEW `rep_moderation_queue` AS
SELECT
  `q`.`id` AS `question_id`,
  `q`.`body` AS `question_body`,
  `q`.`created_at` AS `asked_at`,
  `u`.`username` AS `asker`,
  `i`.`id` AS `item_id`,
  `i`.`title` AS `item_title`,
  `a`.`id` AS `answer_id`,
  `a`.`body` AS `answer_body`
FROM `questions` AS `q`
JOIN `users` AS `u` ON `u`.`id` = `q`.`user_id`
JOIN `items` AS `i` ON `i`.`id` = `q`.`item_id`
LEFT JOIN `answers` AS `a` ON `a`.`question_id` = `q`.`id`
ORDER BY `q`.`created_at` DESC;

SET GLOBAL event_scheduler = ON;

CREATE EVENT IF NOT EXISTS `evt_close_expired_auctions`
ON SCHEDULE EVERY 1 MINUTE
STARTS CURRENT_TIMESTAMP
DO CALL `sp_close_all_expired_auctions`();
