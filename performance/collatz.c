#include <stdio.h>
#include <stdlib.h>

int main() {
	int *out = malloc(1000000 * sizeof(int));

	for (int i = 1; i <= 1000000; i++) {
		long n = i;
		int steps = 0;
		while (n != 1) {
			if (n % 2 == 0) {
				n = n / 2;
			} else {
				n = 3 * n + 1;
			}
			steps++;
		}
		out[i - 1] = steps;
	}

	for (int i = 0; i < 1000000; i++) {
		printf("%d ", out[i]);
	}

	free(out);
	return 0;
}