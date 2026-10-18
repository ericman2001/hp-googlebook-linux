/*
 * ecprobe: send a list of Chrome EC host commands through /dev/cros_ec and
 * print the EC's result code for each, to see which commands the EC accepts
 * from Linux. Built static against the stage3 glibc (see build-images.sh).
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

/* include/uapi/linux/cros_ec_dev.h + struct cros_ec_command from the kernel */
struct cros_ec_command {
	uint32_t version;
	uint32_t command;
	uint32_t outsize;
	uint32_t insize;
	uint32_t result;
	uint8_t data[256];
};

/* The kernel's struct ends in a flexible array: the ioctl size is the header */
struct cros_ec_command_hdr {
	uint32_t version;
	uint32_t command;
	uint32_t outsize;
	uint32_t insize;
	uint32_t result;
};

#define CROS_EC_DEV_IOCXCMD _IOWR(0xEC, 0, struct cros_ec_command_hdr)

struct probe {
	const char *name;
	uint16_t command;
	uint8_t version;
	uint8_t out[8];
	uint8_t outsize;
	uint8_t insize;
};

static const struct probe probes[] = {
	{ "HELLO",               0x0001, 0, { 0xd0, 0xc0, 0xb0, 0xa0 }, 4, 4 },
	{ "GET_VERSION",         0x0002, 0, { 0 }, 0, 100 },
	{ "GET_BOARD_VERSION",   0x0006, 0, { 0 }, 0, 2 },     /* OK from depthcharge */
	{ "GET_CMD_VERSIONS v0", 0x0008, 0, { 0x67 }, 1, 4 },  /* for GET_NEXT_EVENT */
	{ "GET_CMD_VERSIONS v1", 0x0008, 1, { 0x67, 0x00 }, 2, 4 },
	{ "GET_PROTOCOL_INFO",   0x000b, 0, { 0 }, 0, 12 },
	{ "GET_FEATURES",        0x000d, 0, { 0 }, 0, 8 },     /* OK from depthcharge */
	{ "RTC_GET_VALUE",       0x0044, 0, { 0 }, 0, 4 },     /* OK from depthcharge */
	{ "MKBP_STATE",          0x0060, 0, { 0 }, 0, 13 },
	{ "MKBP_INFO",           0x0061, 0, { 0 }, 0, 3 },
	{ "GET_NEXT_EVENT v0",   0x0067, 0, { 0 }, 0, 16 },
	{ "GET_NEXT_EVENT v2",   0x0067, 2, { 0 }, 0, 16 },
	{ "HOST_EVENT GET",      0x00a4, 0, { 0 }, 2, 8 },     /* OK from depthcharge */
	{ "GET_CROS_BOARD_INFO", 0x011f, 0, { 2 }, 8, 4 },     /* OK from depthcharge */
	{ "BATTERY_GET_DYNAMIC", 0x0601, 0, { 0 }, 1, 14 },    /* OK from depthcharge */
};

int main(void)
{
	int fd = open("/dev/cros_ec", O_RDWR);

	if (fd < 0) {
		printf("ecprobe: /dev/cros_ec: %s\n", strerror(errno));
		return 1;
	}

	for (size_t i = 0; i < sizeof(probes) / sizeof(probes[0]); i++) {
		const struct probe *p = &probes[i];
		struct cros_ec_command c = {
			.version = p->version,
			.command = p->command,
			.outsize = p->outsize,
			.insize = p->insize,
		};
		int ret;

		memcpy(c.data, p->out, p->outsize);
		ret = ioctl(fd, CROS_EC_DEV_IOCXCMD, &c);
		/* Compact: NAME=result (or =E for an ioctl error), four per line */
		if (ret < 0 && c.result == 0)
			printf("  %s=E(%d)", p->name, errno);
		else
			printf("  %s=%u", p->name, c.result);
		if (i % 4 == 3)
			printf("\n");
	}
	printf("\n");
	close(fd);
	return 0;
}
