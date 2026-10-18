/*
 * gbkexec: boot another kernel from the running one (kexec_file_load).
 *
 * usage: gbkexec <Image> <initramfs> [cmdline]
 *
 * The cmdline defaults to the current one (/proc/cmdline). The running
 * kernel's device tree is reused. Build static against the stage3 glibc.
 */
#include <fcntl.h>
#include <linux/reboot.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	char cmdline[4096] = "";
	int kfd, ifd;

	if (argc < 3) {
		fprintf(stderr, "usage: %s <Image> <initramfs> [cmdline]\n", argv[0]);
		return 1;
	}
	if (argc > 3) {
		snprintf(cmdline, sizeof(cmdline), "%s", argv[3]);
	} else {
		FILE *f = fopen("/proc/cmdline", "r");

		if (f && fgets(cmdline, sizeof(cmdline), f))
			cmdline[strcspn(cmdline, "\n")] = '\0';
		if (f)
			fclose(f);
	}

	kfd = open(argv[1], O_RDONLY);
	ifd = open(argv[2], O_RDONLY);
	if (kfd < 0 || ifd < 0) {
		perror("open");
		return 1;
	}
	if (syscall(SYS_kexec_file_load, kfd, ifd, strlen(cmdline) + 1, cmdline, 0)) {
		perror("kexec_file_load");
		return 1;
	}
	printf("loaded; booting with: %s\n", cmdline);
	fflush(stdout);
	sync();
	syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
		LINUX_REBOOT_CMD_KEXEC, NULL);
	perror("reboot(KEXEC)");
	return 1;
}
