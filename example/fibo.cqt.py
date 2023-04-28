import chiquito as cqt

circuit = cqt.Circuit("fibo")
circuit.forward_signal('a')
circuit.forward_signal('b')


def fibo_step(this_step, next_step):
    this_step.internal_signal('c')
    this_step.add_contrain(this_step.a + this_step.b == this_step.c)
    this_step.add_transition(this_step.b == next_step.a)
    this_step.add_transition(this_step.c == next_step.b)


def fibo_step_wg(this_step, next_step, witness_note):
    this_step.a = witness_note['a']
    this_step.b = witness_note['b']
    this_step.c = witness_note['a'] + witness_note['b']


def fibo_last_step(this_step, next_step):
    this_step.internal_signal('c')
    this_step.add_contrain(this_step.a + this_step.b == this_step.c)


def fibo_last_step_wg(this_step, next_step, witness_note):
    this_step.a = witness_note['a']
    this_step.b = witness_note['b']
    this_step.c = witness_note['a'] + witness_note['b']


circuit.def_step("fibo_step", fibo_step, fibo_step_wg)
circuit.def_step("fibo_last_step", fibo_last_step, fibo_last_step_wg)
circuit.set_first_step("fibo_step")
circuit.set_last_step("fibo_last_step")


circuit.trace()
circuit.step("fibo_step", {'a': 1, 'b': 1})
note_a = 1
note_b = 2

for i in range(10):
    circuit.step("fibo_step", {'a': note_a, 'b': note_b})
    tmp = note_b
    note_b = note_a + note_b
    note_a = tmp

circuit.step("fibo_last_step", {'a': note_a, 'b': note_b})
circuit.done()
print(circuit)
compiler = cqt.Compiler()
print(compiler.compile(circuit))
