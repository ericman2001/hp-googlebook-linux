/*
 * Show red/green/blue stripes on the first connected DRM connector for a
 * few seconds, bypassing fbcon.
 * usage: drmstripes [/dev/dri/cardN] [seconds] [mode index] [max bpc]
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

int main(int argc, char **argv)
{
	const char *path = argc > 1 ? argv[1] : "/dev/dri/card1";
	int secs = argc > 2 ? atoi(argv[2]) : 20;
	int mode_idx = argc > 3 ? atoi(argv[3]) : 0;
	int max_bpc = argc > 4 ? atoi(argv[4]) : 0;
	int fd = open(path, O_RDWR | O_CLOEXEC);
	if (fd < 0 || drmSetMaster(fd)) { perror(path); return 1; }

	drmModeRes *res = drmModeGetResources(fd);
	drmModeConnector *conn = NULL;
	for (int i = 0; i < res->count_connectors; i++) {
		conn = drmModeGetConnector(fd, res->connectors[i]);
		if (conn->connection == DRM_MODE_CONNECTED && conn->count_modes)
			break;
		drmModeFreeConnector(conn);
		conn = NULL;
	}
	if (!conn) { fprintf(stderr, "no connected connector\n"); return 1; }
	if (mode_idx >= conn->count_modes) { fprintf(stderr, "no mode %d\n", mode_idx); return 1; }
	drmModeModeInfo mode = conn->modes[mode_idx];
	if (max_bpc) {
		drmModeObjectProperties *props = drmModeObjectGetProperties(fd, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR);
		for (uint32_t i = 0; i < props->count_props; i++) {
			drmModePropertyRes *pr = drmModeGetProperty(fd, props->props[i]);
			if (!strcmp(pr->name, "max bpc") &&
			    drmModeObjectSetProperty(fd, conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, pr->prop_id, max_bpc))
				perror("set max bpc");
			drmModeFreeProperty(pr);
		}
	}
	drmModeEncoder *enc = drmModeGetEncoder(fd, conn->encoder_id ? conn->encoder_id : conn->encoders[0]);
	uint32_t crtc = enc->crtc_id;
	for (int i = 0; !crtc && i < res->count_crtcs; i++)
		if (enc->possible_crtcs & (1 << i))
			crtc = res->crtcs[i];
	printf("connector %u, crtc %u, mode %s@%u\n", conn->connector_id, crtc, mode.name, mode.vrefresh);

	struct drm_mode_create_dumb cd = { .width = mode.hdisplay, .height = mode.vdisplay, .bpp = 32 };
	if (drmIoctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &cd)) { perror("create_dumb"); return 1; }
	uint32_t fb;
	if (drmModeAddFB(fd, cd.width, cd.height, 24, 32, cd.pitch, cd.handle, &fb)) { perror("addfb"); return 1; }
	struct drm_mode_map_dumb md = { .handle = cd.handle };
	if (drmIoctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &md)) { perror("map_dumb"); return 1; }
	uint8_t *p = mmap(NULL, cd.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, md.offset);
	if (p == MAP_FAILED) { perror("mmap"); return 1; }
	static const uint32_t colors[] = { 0xffff0000, 0xff00ff00, 0xff0000ff, 0xffffffff };
	for (uint32_t y = 0; y < cd.height; y++) {
		uint32_t *row = (uint32_t *)(p + y * cd.pitch);
		for (uint32_t x = 0; x < cd.width; x++)
			row[x] = colors[x * 4 / cd.width];
	}
	/* Switch the output off first, so the mode is set from scratch */
	if (drmModeSetCrtc(fd, crtc, 0, 0, 0, NULL, 0, NULL))
		perror("setcrtc off");
	sleep(1);
	if (drmModeSetCrtc(fd, crtc, fb, 0, 0, &conn->connector_id, 1, &mode)) { perror("setcrtc"); return 1; }
	printf("showing stripes for %d s\n", secs);
	fflush(stdout);
	sleep(secs);
	return 0;
}
