#define _GNU_SOURCE

#include <errno.h>
#include <math.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static int query_ms(const char *path) {
    const char *p = strstr(path, "ms=");
    if (p == NULL) {
        return 100;
    }
    int value = atoi(p + 3);
    if (value < 0) {
        return 100;
    }
    if (value > 30000) {
        return 30000;
    }
    return value;
}

static void cpu_work(int duration_ms) {
    struct timespec start;
    clock_gettime(CLOCK_MONOTONIC, &start);
    double value = 0.0001;
    for (;;) {
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        long elapsed_ms = (now.tv_sec - start.tv_sec) * 1000L + (now.tv_nsec - start.tv_nsec) / 1000000L;
        if (elapsed_ms >= duration_ms) {
            break;
        }
        value += sqrt(value);
    }
}

static void respond(int fd, int status, const char *message) {
    char body[512];
    int body_len = snprintf(
        body,
        sizeof(body),
        "{\"service\":\"demo-service\",\"message\":\"%s\"}\n",
        message
    );
    dprintf(
        fd,
        "HTTP/1.1 %d OK\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%s",
        status,
        body_len,
        body
    );
}

static void handle_client(int fd) {
    char buffer[2048] = {0};
    ssize_t n = read(fd, buffer, sizeof(buffer) - 1);
    if (n <= 0) {
        return;
    }

    char method[16] = {0};
    char path[1024] = {0};
    sscanf(buffer, "%15s %1023s", method, path);
    if (strcmp(method, "GET") != 0) {
        respond(fd, 405, "method not allowed");
        return;
    }
    if (strcmp(path, "/") == 0) {
        respond(fd, 200, "ok");
        return;
    }
    if (strcmp(path, "/healthz") == 0) {
        respond(fd, 200, "healthy");
        return;
    }
    if (strcmp(path, "/readyz") == 0) {
        respond(fd, 200, "ready");
        return;
    }
    if (strncmp(path, "/work", 5) == 0) {
        cpu_work(query_ms(path));
        respond(fd, 200, "work complete");
        return;
    }
    respond(fd, 404, "not found");
}

int main(void) {
    signal(SIGPIPE, SIG_IGN);

    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        return 1;
    }

    int enabled = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof(enabled));

    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(8080);

    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("bind");
        return 1;
    }
    if (listen(server_fd, 128) < 0) {
        perror("listen");
        return 1;
    }

    for (;;) {
        int client_fd = accept(server_fd, NULL, NULL);
        if (client_fd < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("accept");
            continue;
        }
        handle_client(client_fd);
        close(client_fd);
    }
}
