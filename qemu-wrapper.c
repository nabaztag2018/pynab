// From https://wiki.gentoo.org/wiki/Embedded_Handbook/General/Compiling_with_qemu_user_chroot
/*
 * pass arguments to qemu binary
 */

#include <string.h>
#include <unistd.h>

int main(int argc, char **argv, char **envp) {
	char *newargv[argc + 3];

	newargv[0] = argv[0];
	newargv[1] = "-cpu";
	newargv[2] = "arm1176"; /* here you can set the cpu you are building for */

	memcpy(&newargv[3], &argv[1], sizeof(*argv) * (argc -1));
	newargv[argc + 2] = NULL;
	return execve("/usr/bin/qemu-arm-static0", newargv, envp);
}
