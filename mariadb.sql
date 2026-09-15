-- phpMyAdmin SQL Dump
-- version 5.2.3
-- https://www.phpmyadmin.net/
--
-- Host: mariadb:3306
-- Generation Time: Sep 11, 2026 at 04:48 AM
-- Server version: 11.8.9-MariaDB-ubu2404
-- PHP Version: 8.3.33

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `db`
--
CREATE DATABASE IF NOT EXISTS `db` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_uca1400_ai_ci;
USE `db`;

-- --------------------------------------------------------

--
-- Table structure for table `allowed_file_types`
--

CREATE TABLE `allowed_file_types` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `extension` varchar(30) NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `allowed_file_types`
--

INSERT INTO `allowed_file_types` (`id`, `extension`, `enabled`, `created_at`) VALUES
(2, 'xlsx', 1, '2026-09-07 08:34:34'),
(3, 'jpg', 1, '2026-09-07 08:34:34'),
(4, 'png', 1, '2026-09-07 08:34:34'),
(5, 'pdf', 1, '2026-09-07 10:06:22'),
(6, 'zip', 1, '2026-09-14 00:00:00'),
(7, 'csv', 1, '2026-09-14 00:00:00'),
(8, 'rar', 1, '2026-09-14 00:00:00'),
(9, 'xls', 1, '2026-09-14 00:00:00'),
(10, 'txt', 1, '2026-09-14 00:00:00'),
(11, 'dwg', 1, '2026-09-14 00:00:00'),
(12, 'dwf', 1, '2026-09-14 00:00:00'),
(13, 'rvt', 1, '2026-09-14 00:00:00'),
(14, 'rte', 1, '2026-09-14 00:00:00'),
(15, 'rfa', 1, '2026-09-14 00:00:00'),
(16, 'ifc', 1, '2026-09-14 00:00:00'),
(17, 'nwd', 1, '2026-09-14 00:00:00'),
(18, 'nwf', 1, '2026-09-14 00:00:00'),
(19, 'skp', 1, '2026-09-14 00:00:00'),
(20, 'drs', 1, '2026-09-14 00:00:00'),
(21, 'ies', 1, '2026-09-14 00:00:00'),
(22, 'hdri', 1, '2026-09-14 00:00:00'),
(23, 'bmp', 1, '2026-09-14 00:00:00'),
(24, 'dds', 1, '2026-09-14 00:00:00'),
(25, 'exr', 1, '2026-09-14 00:00:00');

-- --------------------------------------------------------

--
-- Table structure for table `audit_logs`
--

CREATE TABLE `audit_logs` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `user_email` varchar(254) NOT NULL,
  `action` varchar(80) NOT NULL,
  `detail` varchar(255) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `audit_logs`
--

INSERT INTO `audit_logs` (`id`, `user_email`, `action`, `detail`, `ip_address`, `created_at`) VALUES
(1, 'admin@flowvault.test', 'password_verified', NULL, '127.0.0.1', '2026-09-07 08:43:01'),
(2, 'aitllandyhome@gmail.com', 'password_verified', NULL, '127.0.0.1', '2026-09-07 08:44:13'),
(3, 'aitllandyhome@gmail.com', 'password_verified', NULL, '127.0.0.1', '2026-09-07 08:48:41'),
(4, 'aitllandyhome@gmail.com', 'login_completed', NULL, '127.0.0.1', '2026-09-07 08:49:05'),
(5, 'aitllandyhome@gmail.com', 'password_verified', NULL, '127.0.0.1', '2026-09-07 08:49:36'),
(6, 'aitllandyhome@gmail.com', 'login_completed', NULL, '127.0.0.1', '2026-09-07 08:49:56'),
(7, 'aitllandyhome@gmail.com', 'otp_resent', NULL, '127.0.0.1', '2026-09-07 08:58:44'),
(8, 'aitllandyhome@gmail.com', 'login_completed', NULL, '127.0.0.1', '2026-09-07 08:58:56'),
(9, 'aitllandyhome@gmail.com', 'request_get', 'management.file_types · /admin/file-types · HTTP 200', '127.0.0.1', '2026-09-07 10:24:57'),
(10, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 10:24:57'),
(11, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 10:46:23'),
(12, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 10:46:35'),
(13, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 10:46:58'),
(14, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 10:47:01'),
(15, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 10:47:02'),
(16, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 10:48:03'),
(17, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-07 11:01:02'),
(18, 'aitllandyhome@gmail.com', 'password_verified', NULL, '127.0.0.1', '2026-09-11 01:33:56'),
(19, 'aitllandyhome@gmail.com', 'login_completed', NULL, '127.0.0.1', '2026-09-11 01:34:34'),
(20, 'aitllandyhome@gmail.com', 'request_post', 'auth.verify_otp · /verify-otp · HTTP 302', '127.0.0.1', '2026-09-11 01:34:34'),
(21, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:34:34'),
(22, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:34:36'),
(23, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:34:37'),
(24, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:34:40'),
(25, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:33'),
(26, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:34'),
(27, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:34'),
(28, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:35'),
(29, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:35'),
(30, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:36'),
(31, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:36'),
(32, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:36'),
(33, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:37'),
(34, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:37'),
(35, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:37:58'),
(36, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:38:01'),
(37, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:38:06'),
(38, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:38:09'),
(39, 'aitllandyhome@gmail.com', 'request_get', 'management.users_permissions · /admin/users · HTTP 200', '127.0.0.1', '2026-09-11 01:39:15'),
(40, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 01:39:17'),
(41, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/upload · HTTP 200', '127.0.0.1', '2026-09-11 01:39:19'),
(42, 'aitllandyhome@gmail.com', 'request_get', 'management.file_types · /admin/file-types · HTTP 200', '127.0.0.1', '2026-09-11 01:39:21'),
(43, 'aitllandyhome@gmail.com', 'request_get', 'management.departments · /admin/departments · HTTP 200', '127.0.0.1', '2026-09-11 01:39:25'),
(44, 'aitllandyhome@gmail.com', 'request_get', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:39:27'),
(45, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-11 01:39:30'),
(46, 'aitllandyhome@gmail.com', 'request_get', 'auth.otp_gmail_settings · /admin/otp-gmail-settings · HTTP 200', '127.0.0.1', '2026-09-11 01:39:32'),
(47, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-11 01:39:36'),
(48, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:39:48'),
(49, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 01:39:50'),
(50, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 01:39:52'),
(51, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 01:39:52'),
(52, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 01:39:55'),
(53, 'aitllandyhome@gmail.com', 'request_get', 'unknown · /favicon.ico · HTTP 404', '127.0.0.1', '2026-09-11 01:39:56'),
(54, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 01:39:56'),
(55, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 01:40:02'),
(56, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:40:05'),
(57, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:40:12'),
(58, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:40:33'),
(59, 'aitllandyhome@gmail.com', 'request_get', 'management.shared_with_me · /shared-with-me · HTTP 200', '127.0.0.1', '2026-09-11 01:41:54'),
(60, 'aitllandyhome@gmail.com', 'request_get', 'management.users_permissions · /admin/users · HTTP 200', '127.0.0.1', '2026-09-11 01:41:57'),
(61, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/upload · HTTP 200', '127.0.0.1', '2026-09-11 01:41:59'),
(62, 'aitllandyhome@gmail.com', 'request_get', 'management.users_permissions · /admin/users · HTTP 200', '127.0.0.1', '2026-09-11 01:42:01'),
(63, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:45:54'),
(64, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:46:06'),
(65, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:48:39'),
(66, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 01:55:49'),
(67, 'aitllandyhome@gmail.com', 'request_get', 'management.shared_with_me · /shared-with-me · HTTP 200', '127.0.0.1', '2026-09-11 01:55:54'),
(68, 'aitllandyhome@gmail.com', 'request_get', 'management.users_permissions · /admin/users · HTTP 200', '127.0.0.1', '2026-09-11 01:56:03'),
(69, 'aitllandyhome@gmail.com', 'request_get', 'management.departments · /admin/departments · HTTP 200', '127.0.0.1', '2026-09-11 01:56:12'),
(70, 'aitllandyhome@gmail.com', 'request_get', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:56:14'),
(71, 'aitllandyhome@gmail.com', 'request_get', 'management.departments · /admin/departments · HTTP 200', '127.0.0.1', '2026-09-11 01:56:17'),
(72, 'aitllandyhome@gmail.com', 'request_get', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:12'),
(73, 'aitllandyhome@gmail.com', 'permission_tier_save', 'T1', '127.0.0.1', '2026-09-11 01:58:21'),
(74, 'aitllandyhome@gmail.com', 'request_post', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:22'),
(75, 'aitllandyhome@gmail.com', 'permission_tier_save', 'T2', '127.0.0.1', '2026-09-11 01:58:22'),
(76, 'aitllandyhome@gmail.com', 'request_post', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:22'),
(77, 'aitllandyhome@gmail.com', 'permission_tier_save', 'T3', '127.0.0.1', '2026-09-11 01:58:23'),
(78, 'aitllandyhome@gmail.com', 'request_post', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:23'),
(79, 'aitllandyhome@gmail.com', 'permission_tier_save', 'T3', '127.0.0.1', '2026-09-11 01:58:26'),
(80, 'aitllandyhome@gmail.com', 'request_post', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:26'),
(81, 'aitllandyhome@gmail.com', 'permission_tier_save', 'T1', '127.0.0.1', '2026-09-11 01:58:40'),
(82, 'aitllandyhome@gmail.com', 'request_post', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:40'),
(83, 'aitllandyhome@gmail.com', 'permission_tier_save', 'T2', '127.0.0.1', '2026-09-11 01:58:41'),
(84, 'aitllandyhome@gmail.com', 'request_post', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:41'),
(85, 'aitllandyhome@gmail.com', 'permission_tier_save', 'T3', '127.0.0.1', '2026-09-11 01:58:41'),
(86, 'aitllandyhome@gmail.com', 'request_post', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 01:58:41'),
(87, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:08:16'),
(88, 'aitllandyhome@gmail.com', 'request_get', 'management.shared_with_me · /shared-with-me · HTTP 200', '127.0.0.1', '2026-09-11 02:08:18'),
(89, 'aitllandyhome@gmail.com', 'request_get', 'management.users_permissions · /admin/users · HTTP 200', '127.0.0.1', '2026-09-11 02:08:20'),
(90, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:09:01'),
(91, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:09:03'),
(92, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:09:06'),
(93, 'aitllandyhome@gmail.com', 'request_get', 'management.shared_with_me · /shared-with-me · HTTP 200', '127.0.0.1', '2026-09-11 02:49:10'),
(94, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:49:12'),
(95, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:49:15'),
(96, 'aitllandyhome@gmail.com', 'request_get', 'management.users_permissions · /admin/users · HTTP 200', '127.0.0.1', '2026-09-11 02:49:26'),
(97, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/download · HTTP 200', '127.0.0.1', '2026-09-11 02:49:32'),
(98, 'aitllandyhome@gmail.com', 'request_get', 'management.usage · /admin/usage/upload · HTTP 200', '127.0.0.1', '2026-09-11 02:49:37'),
(99, 'aitllandyhome@gmail.com', 'request_get', 'management.file_types · /admin/file-types · HTTP 200', '127.0.0.1', '2026-09-11 02:49:52'),
(100, 'aitllandyhome@gmail.com', 'request_get', 'management.departments · /admin/departments · HTTP 200', '127.0.0.1', '2026-09-11 02:49:56'),
(101, 'aitllandyhome@gmail.com', 'request_get', 'management.permission_tiers · /admin/permission-tiers · HTTP 200', '127.0.0.1', '2026-09-11 02:49:58'),
(102, 'aitllandyhome@gmail.com', 'request_get', 'auth.admin_logs · /admin/logs · HTTP 200', '127.0.0.1', '2026-09-11 02:50:04'),
(103, 'aitllandyhome@gmail.com', 'request_get', 'auth.otp_gmail_settings · /admin/otp-gmail-settings · HTTP 200', '127.0.0.1', '2026-09-11 02:50:08'),
(104, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:50:16'),
(105, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:50:20'),
(106, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:50:27'),
(107, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 02:50:29'),
(108, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 03:25:36'),
(109, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 03:28:31'),
(110, 'aitllandyhome@gmail.com', 'request_get', 'files.my_files · /my-files/ · HTTP 200', '127.0.0.1', '2026-09-11 03:28:33');

-- --------------------------------------------------------

--
-- Table structure for table `auth_login_attempts`
--

CREATE TABLE `auth_login_attempts` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `scope_key` char(64) NOT NULL,
  `attempted_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `departments`
--

CREATE TABLE `departments` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `name` varchar(100) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `departments`
--

INSERT INTO `departments` (`id`, `name`, `created_at`) VALUES
(3, 'ฝ่ายผลิตภัณฑ์ Trendy', '2026-09-14 00:00:00'),
(4, 'ฝ่ายผลิตภัณฑ์ Landy', '2026-09-14 00:00:00'),
(5, 'ฝ่ายผลิตภัณฑ์ Landy Grand', '2026-09-14 00:00:00'),
(6, 'ฝ่ายขาย', '2026-09-14 00:00:00'),
(7, 'ฝ่ายเขียนแบบและประมาณราคา', '2026-09-14 00:00:00'),
(8, 'ฝ่ายวิศวกรรม', '2026-09-14 00:00:00'),
(9, 'ฝ่ายก่อสร้าง', '2026-09-14 00:00:00'),
(10, 'ฝ่ายจัดหา', '2026-09-14 00:00:00');

-- --------------------------------------------------------

--
-- Table structure for table `files`
--

CREATE TABLE `files` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `owner_id` bigint(20) UNSIGNED NOT NULL,
  `folder_id` bigint(20) UNSIGNED DEFAULT NULL,
  `original_name` varchar(255) NOT NULL,
  `stored_name` varchar(300) NOT NULL,
  `mime_type` varchar(255) NOT NULL,
  `size_bytes` bigint(20) UNSIGNED NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `file_shares`
--

CREATE TABLE `file_shares` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `item_name` varchar(255) NOT NULL,
  `recipient_email` varchar(254) NOT NULL,
  `permission` varchar(20) NOT NULL DEFAULT 'view',
  `shared_by` varchar(254) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `folders`
--

CREATE TABLE `folders` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `owner_id` bigint(20) UNSIGNED NOT NULL,
  `parent_id` bigint(20) UNSIGNED DEFAULT NULL,
  `name` varchar(100) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `folders`
--

INSERT INTO `folders` (`id`, `owner_id`, `parent_id`, `name`, `created_at`) VALUES
(1, 8, NULL, '(1) ???????', '2026-09-07 09:21:02'),
(2, 8, NULL, '(2) Project', '2026-09-07 09:21:02'),
(3, 8, 1, '(1.1) ????????????', '2026-09-07 09:21:02'),
(4, 8, 3, '(1.1.1) TRENDY', '2026-09-07 09:21:02'),
(5, 8, 3, '(1.1.2) LANDY', '2026-09-07 09:21:02'),
(6, 8, 3, '(1.1.3) LANDY GRAND', '2026-09-07 09:21:02'),
(7, 8, 1, '(1.2) ??????????????', '2026-09-07 09:21:02'),
(8, 8, 7, '(1.2.1) TRENDY', '2026-09-07 09:21:02'),
(9, 8, 7, '(1.2.2) LANDY', '2026-09-07 09:21:02'),
(10, 8, 7, '(1.2.3) LANDY GRAND', '2026-09-07 09:21:02'),
(11, 8, 1, '(1.3) Family/???????', '2026-09-07 09:21:02'),
(12, 8, 11, '(1.3.1) COMPANY-MASTER-FAMILY', '2026-09-07 09:21:02'),
(13, 8, 11, '(1.3.2) Model D5', '2026-09-07 09:21:02');

-- --------------------------------------------------------

--
-- Table structure for table `recycle_bin_items`
--

CREATE TABLE `recycle_bin_items` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `item_type` varchar(10) NOT NULL,
  `storage_root` varchar(1024) NOT NULL,
  `original_path` varchar(1024) NOT NULL,
  `trash_token` char(32) NOT NULL,
  `deleted_by` varchar(254) NOT NULL,
  `deleted_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `expires_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `otp_gmail_settings`
--

CREATE TABLE `otp_gmail_settings` (
  `id` tinyint(3) UNSIGNED NOT NULL,
  `sender_email` varchar(254) NOT NULL,
  `encrypted_app_password` text NOT NULL,
  `smtp_host` varchar(255) NOT NULL DEFAULT 'smtp.gmail.com',
  `smtp_port` smallint(5) UNSIGNED NOT NULL DEFAULT 587,
  `use_tls` tinyint(1) NOT NULL DEFAULT 1,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `enabled` tinyint(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `otp_gmail_settings`
--

INSERT INTO `otp_gmail_settings` (`id`, `sender_email`, `encrypted_app_password`, `smtp_host`, `smtp_port`, `use_tls`, `updated_at`, `enabled`) VALUES
(1, 'bd.aidev@landyhome.co.th', 'gAAAAABqnmPEPS8mE51DPleL-qUkOr5We01nhWkLEBwmR4Ck-85RkDQ24vGoY4cPHo8bIXv9U2M6HOXqms8UqYI1BwCpFV7e5RJCQaJCPQj08Q5Mm3Vzp0Y=', 'smtp.gmail.com', 587, 1, '2026-09-07 07:12:04', 1);

-- --------------------------------------------------------

--
-- Table structure for table `permission_tiers`
--

CREATE TABLE `permission_tiers` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `tier_code` varchar(30) NOT NULL,
  `description` varchar(255) NOT NULL,
  `can_preview` tinyint(1) NOT NULL DEFAULT 0,
  `can_download` tinyint(1) NOT NULL DEFAULT 0,
  `can_create` tinyint(1) NOT NULL DEFAULT 0,
  `can_modify` tinyint(1) NOT NULL DEFAULT 0,
  `can_delete` tinyint(1) NOT NULL DEFAULT 0,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `permission_tiers`
--

INSERT INTO `permission_tiers` (`id`, `tier_code`, `description`, `can_preview`, `can_download`, `can_create`, `can_modify`, `can_delete`, `enabled`, `created_at`) VALUES
(1, 'T1', 'Full file access — Preview, Download, Create, Upload, Share, Rename, Move, Overwrite, Delete', 1, 1, 1, 1, 1, 1, '2026-09-07 10:00:32'),
(2, 'T2', 'Create and modify, no delete — Preview, Download, Create, Upload, Share, Rename, Move, Overwrite', 1, 1, 1, 1, 0, 1, '2026-09-07 10:00:32'),
(3, 'T3', 'Preview and download — Preview, Download', 1, 1, 0, 0, 0, 1, '2026-09-07 10:00:32'),
(4, 'T4', 'Preview only — Preview', 1, 0, 0, 0, 0, 1, '2026-09-07 10:00:32');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `email` varchar(254) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `role` varchar(30) NOT NULL DEFAULT 'user',
  `department` varchar(100) DEFAULT NULL,
  `permission_tier` varchar(30) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `email`, `password_hash`, `created_at`, `role`, `department`, `permission_tier`) VALUES
(6, 'admin@flowvault.test', 'scrypt:32768:8:1$3X5q2lU54Iwg80PL$eba7d02f88680c0183df282996f1efa26789ec6618f5f63f9bbcb32e9ed8231a4c9389ede30501ae4b202f0749a7986614a39f674c2a3face0f93fda06dd39f1', '2026-09-07 07:07:08', 'department_admin', 'General', NULL),
(7, 'user@flowvault.test', 'scrypt:32768:8:1$SA6Ct1LiYEC7eCKr$61e0858e1a6965f5d7a8ce24fee8c074a2164d2a9057c61011c6fe389d435e43e4557706fec7d6a302ed8241aa0e9c4a52366fcc2068aa63e759fca4dcf2f34f', '2026-09-07 07:07:08', 'user', NULL, NULL),
(8, 'aitllandyhome@gmail.com', 'scrypt:32768:8:1$BF2DW5rGUjYKAZlb$c5eed517d99ac8bc8e6bec78c94a54af70a354c765300c0816ec329cd6c49016159fd2d0f6856bd5d4c1f9cb07d9a47fb18e4aec37c602034740972fb05d9376', '2026-09-07 07:53:56', 'super_admin', NULL, NULL);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `allowed_file_types`
--
ALTER TABLE `allowed_file_types`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `extension` (`extension`);

--
-- Indexes for table `audit_logs`
--
ALTER TABLE `audit_logs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_audit_logs_user_time` (`user_email`,`created_at`),
  ADD KEY `idx_audit_logs_time` (`created_at`);

--
-- Indexes for table `auth_login_attempts`
--
ALTER TABLE `auth_login_attempts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_auth_login_attempts_scope_time` (`scope_key`,`attempted_at`);

--
-- Indexes for table `departments`
--
ALTER TABLE `departments`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Indexes for table `files`
--
ALTER TABLE `files`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_files_stored_name` (`stored_name`),
  ADD KEY `ix_files_owner_folder_created` (`owner_id`,`folder_id`,`created_at`),
  ADD KEY `fk_files_folder` (`folder_id`);

--
-- Indexes for table `file_shares`
--
ALTER TABLE `file_shares`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_shares_recipient` (`recipient_email`);

--
-- Indexes for table `folders`
--
ALTER TABLE `folders`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_folders_owner_parent_name` (`owner_id`,`parent_id`,`name`),
  ADD KEY `fk_folders_parent` (`parent_id`);

--
-- Indexes for table `otp_gmail_settings`
--
ALTER TABLE `otp_gmail_settings`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `recycle_bin_items`
--
ALTER TABLE `recycle_bin_items`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `trash_token` (`trash_token`),
  ADD KEY `idx_recycle_bin_scope_expiry` (`storage_root`(255),`expires_at`);

--
-- Indexes for table `permission_tiers`
--
ALTER TABLE `permission_tiers`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `tier_code` (`tier_code`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_users_email` (`email`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `allowed_file_types`
--
ALTER TABLE `allowed_file_types`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=26;

--
-- AUTO_INCREMENT for table `audit_logs`
--
ALTER TABLE `audit_logs`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=111;

--
-- AUTO_INCREMENT for table `auth_login_attempts`
--
ALTER TABLE `auth_login_attempts`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- AUTO_INCREMENT for table `departments`
--
ALTER TABLE `departments`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `files`
--
ALTER TABLE `files`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `file_shares`
--
ALTER TABLE `file_shares`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `folders`
--
ALTER TABLE `folders`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- AUTO_INCREMENT for table `permission_tiers`
--
ALTER TABLE `permission_tiers`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `recycle_bin_items`
--
ALTER TABLE `recycle_bin_items`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `files`
--
ALTER TABLE `files`
  ADD CONSTRAINT `fk_files_folder` FOREIGN KEY (`folder_id`) REFERENCES `folders` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_files_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `folders`
--
ALTER TABLE `folders`
  ADD CONSTRAINT `fk_folders_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_folders_parent` FOREIGN KEY (`parent_id`) REFERENCES `folders` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
