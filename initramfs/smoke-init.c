/*
 * Minimal freestanding /init for the first Googlebook boot test.
 *
 * No libc: raw aarch64 syscalls only. It mounts the pseudo filesystems,
 * prints the kernel version and uptime to the console, then prints a
 * heartbeat every 10 seconds so a live system is distinguishable from a hang.
 * After REBOOT_AFTER heartbeats it reboots the machine (PSCI SYSTEM_RESET),
 * so reaching userspace is visible even without a working display.
 *
 * Build: clang --target=aarch64-linux-gnu -O2 -static -nostdlib -ffreestanding
 *        -fno-stack-protector -fuse-ld=lld -o init smoke-init.c
 */

typedef unsigned long size_t;
typedef long ssize_t;

#define SYS_mkdirat	34
#define SYS_mount	40
#define SYS_openat	56
#define SYS_close	57
#define SYS_read	63
#define SYS_write	64
#define SYS_nanosleep	101
#define SYS_reboot	142
#define SYS_exit	93

#define LINUX_REBOOT_MAGIC1	0xfee1dead
#define LINUX_REBOOT_MAGIC2	672274793
#define LINUX_REBOOT_CMD_RESTART	0x01234567

#define REBOOT_AFTER	2	/* heartbeats, 10 s apart */

#define AT_FDCWD	-100
#define O_RDONLY	0
#define O_RDWR		2

static long syscall6(long n, long a, long b, long c, long d, long e, long f)
{
	register long x8 __asm__("x8") = n;
	register long x0 __asm__("x0") = a;
	register long x1 __asm__("x1") = b;
	register long x2 __asm__("x2") = c;
	register long x3 __asm__("x3") = d;
	register long x4 __asm__("x4") = e;
	register long x5 __asm__("x5") = f;

	__asm__ volatile("svc #0"
			 : "+r"(x0)
			 : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5)
			 : "memory");
	return x0;
}

#define syscall3(n, a, b, c) syscall6(n, (long)(a), (long)(b), (long)(c), 0, 0, 0)

static int console = 1;

static size_t len(const char *s)
{
	size_t n = 0;

	while (s[n])
		n++;
	return n;
}

static void puts_(const char *s)
{
	syscall3(SYS_write, console, s, len(s));
}

static void mount_(const char *src, const char *dst, const char *type)
{
	syscall3(SYS_mkdirat, AT_FDCWD, dst, 0755);
	syscall6(SYS_mount, (long)src, (long)dst, (long)type, 0, 0, 0);
}

/* Copy a small file (e.g. /proc/version) to the console. */
static void cat(const char *path)
{
	char buf[512];
	long fd = syscall3(SYS_openat, AT_FDCWD, path, O_RDONLY);
	ssize_t n;

	if (fd < 0) {
		puts_("(cannot open ");
		puts_(path);
		puts_(")\n");
		return;
	}
	while ((n = syscall3(SYS_read, fd, buf, sizeof(buf))) > 0)
		syscall3(SYS_write, console, buf, n);
	syscall3(SYS_close, fd, 0, 0);
}

void _start(void)
{
	struct { long sec, nsec; } ten = { 10, 0 };
	long fd;
	int beats = 0;

	mount_("devtmpfs", "/dev", "devtmpfs");
	mount_("proc", "/proc", "proc");
	mount_("sysfs", "/sys", "sysfs");

	fd = syscall3(SYS_openat, AT_FDCWD, "/dev/console", O_RDWR);
	if (fd >= 0)
		console = fd;

	puts_("\n\n*** Gentoo Googlebook smoke test: init is running ***\n\n");
	cat("/proc/version");
	puts_("cmdline: ");
	cat("/proc/cmdline");
	puts_("model: ");
	cat("/sys/firmware/devicetree/base/model");
	puts_("\n");

	for (;;) {
		puts_("init alive, uptime: ");
		cat("/proc/uptime");
		if (beats++ == REBOOT_AFTER) {
			puts_("rebooting\n");
			syscall6(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
				 LINUX_REBOOT_CMD_RESTART, 0, 0, 0);
		}
		syscall6(SYS_nanosleep, (long)&ten, 0, 0, 0, 0, 0);
	}
}
