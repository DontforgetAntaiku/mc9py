CC = i686-w64-mingw32-gcc
CFLAGS = -O2 -Wall -Wextra -std=gnu11
all: mc9hook.dll mc9launch.exe
mc9hook.dll: hook.c scan.c scan.h
	$(CC) $(CFLAGS) -shared -static-libgcc -o $@ hook.c scan.c
mc9launch.exe: launch.c
	$(CC) $(CFLAGS) -static-libgcc -o $@ launch.c
clean:
	rm -f *.dll *.exe

# put the build into the Python package so `python -m build` ships it in the wheel (CI does this before building)
package: all
	mkdir -p ../src/mc9/_native
	cp mc9hook.dll mc9launch.exe signatures.txt ../src/mc9/_native/
