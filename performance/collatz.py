out = [] # number of steps

# loop 1 to 1M
for i in range(1, 1000001):
	n = i
	steps = 0
	while n != 1:
		if n % 2 == 0:
			n = n // 2
		else:
			n = 3*n + 1
		steps += 1
	out.append(steps)

print(out)


