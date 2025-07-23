/*
 Navicat Premium Dump SQL

 Source Server         : 05
 Source Server Type    : MariaDB
 Source Server Version : 110802 (11.8.2-MariaDB)
 Source Host           : 192.168.0.5:3306
 Source Schema         : new_version_tur

 Target Server Type    : MariaDB
 Target Server Version : 110802 (11.8.2-MariaDB)
 File Encoding         : 65001

 Date: 23/07/2025 16:40:55
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for tur_chat_history
-- ----------------------------
DROP TABLE IF EXISTS `tur_chat_history`;
CREATE TABLE `tur_chat_history`  (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `user_id` int(11) NOT NULL COMMENT '用户ID',
  `chat_session_id` bigint(20) NOT NULL COMMENT '会话ID',
  `sender` enum('ai','user') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '发送者',
  `text` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '文本',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  INDEX `chat_session_id`(`chat_session_id` ASC) USING BTREE,
  CONSTRAINT `tur_chat_history_ibfk_1` FOREIGN KEY (`chat_session_id`) REFERENCES `tur_chat_sessions` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for tur_chat_sessions
-- ----------------------------
DROP TABLE IF EXISTS `tur_chat_sessions`;
CREATE TABLE `tur_chat_sessions`  (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `user_id` int(11) NOT NULL COMMENT '用户ID',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '会话标题（通常第一句话）',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  CONSTRAINT `tur_chat_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `tur_users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for tur_users
-- ----------------------------
DROP TABLE IF EXISTS `tur_users`;
CREATE TABLE `tur_users`  (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `phone_number` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '手机号码',
  `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码哈希',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `phone_number`(`phone_number` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
