/*
 * ecspi: talk to the Chrome EC over raw spidev, bypassing cros_ec_spi.
 *
 * Sends an EC_CMD_HELLO host command (protocol v3) at several SPI clock
 * speeds and modes, and prints what the EC clocks back after the request:
 * the preamble bytes (EC_SPI_* status markers) and the response frame that
 * follows the 0xec frame-start byte.
 *
 * usage: ecspi [/dev/spidevB.C]
 */
#include <fcntl.h>
#include <linux/spi/spidev.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define EC_SPI_FRAME_START	0xec
#define REPLY_BYTES		160

static const uint32_t speeds[] = { 3000000, 1000000, 400000, 100000 };

/* struct ec_host_request + struct ec_params_hello, checksum makes the sum 0 */
static int build_hello(uint8_t *buf)
{
	uint8_t req[12] = {
		3,		/* struct_version */
		0,		/* checksum */
		0x01, 0x00,	/* command: EC_CMD_HELLO */
		0,		/* command_version */
		0,		/* reserved */
		4, 0,		/* data_len */
		0xd0, 0xc0, 0xb0, 0xa0,	/* in_data = 0xa0b0c0d0 */
	};
	uint8_t sum = 0;

	for (int i = 0; i < 12; i++)
		sum += req[i];
	req[1] = (uint8_t)-sum;
	memcpy(buf, req, sizeof(req));
	return sizeof(req);
}

static void try(int fd, uint32_t speed, uint8_t mode)
{
	uint8_t tx[12 + REPLY_BYTES], rx[sizeof(tx)];
	struct spi_ioc_transfer t = {
		.tx_buf = (uintptr_t)tx,
		.rx_buf = (uintptr_t)rx,
		.len = sizeof(tx),
		.speed_hz = speed,
		.bits_per_word = 8,
	};
	struct timespec gap = { 0, 2 * 1000 * 1000 };
	int n = build_hello(tx), start = -1;

	memset(tx + n, 0xff, sizeof(tx) - n);
	memset(rx, 0, sizeof(rx));
	ioctl(fd, SPI_IOC_WR_MODE, &mode);
	if (ioctl(fd, SPI_IOC_MESSAGE(1), &t) < 0) {
		printf("  %7u Hz mode %u: transfer failed\n", speed, mode);
		return;
	}
	nanosleep(&gap, NULL);	/* let the EC recover between transactions */

	for (int i = n; i < (int)sizeof(rx); i++) {
		if (rx[i] == EC_SPI_FRAME_START) {
			start = i;
			break;
		}
	}
	printf("  %7u Hz mode %u: during req:", speed, mode);
	for (int i = 0; i < n; i++)
		printf("%02x", rx[i]);
	if (start < 0) {
		printf(" no frame; after:");
		for (int i = n; i < n + 12; i++)
			printf(" %02x", rx[i]);
		printf("\n");
		return;
	}
	/* ec_host_response: struct_version, checksum, result(2), data_len(2), reserved(2) */
	printf(" frame@+%d: res %u len %u data", start - n,
	       rx[start + 3] | rx[start + 4] << 8, rx[start + 5] | rx[start + 6] << 8);
	for (int i = start + 9; i < start + 13 && i < (int)sizeof(rx); i++)
		printf(" %02x", rx[i]);
	printf("\n");
}

int main(int argc, char **argv)
{
	const char *dev = argc > 1 ? argv[1] : "/dev/spidev0.0";
	int fd = open(dev, O_RDWR);

	if (fd < 0) {
		perror(dev);
		return 1;
	}
	printf("  EC_CMD_HELLO over %s (expect res 0, data d4 c3 b2 a1):\n", dev);
	for (unsigned int s = 0; s < sizeof(speeds) / sizeof(speeds[0]); s++)
		for (uint8_t mode = 0; mode < 4; mode++)
			try(fd, speeds[s], mode);
	close(fd);
	return 0;
}
