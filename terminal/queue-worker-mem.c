#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;

static void stop_worker(int sig) {
    (void)sig;
    running = 0;
}

int main(int argc, char **argv) {
    size_t kb = 512;

    if (argc >= 2) {
        long parsed = strtol(argv[1], NULL, 10);
        if (parsed > 0) {
            kb = (size_t)parsed;
        }
    }

    size_t bytes = kb * 1024;
    unsigned char *buffer = malloc(bytes);

    if (!buffer) {
        fprintf(stderr, "queue-worker-mem: allocation failed\n");
        return 1;
    }

    for (size_t i = 0; i < bytes; i += 4096) {
        buffer[i] = (unsigned char)(i % 251);
    }

    signal(SIGTERM, stop_worker);
    signal(SIGINT, stop_worker);

    while (running) {
        pause();
    }

    free(buffer);
    return 0;
}
