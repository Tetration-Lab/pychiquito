
from typing import Any
import template

HALO2_CURVE_BN254 = "HALO2_CURVE_BN254"
HALO2_CURVE_BLS12 = "HALO2_CURVE_BLS12"
HALO2_PROOFS_PLONK = "HALO2_PROOFS_PLONK"


class Circuit:
    class Expression:
        def __init__(self, circuit, lhs, rhs, op) -> None:
            self.circuit = circuit
            self.lhs = lhs
            self.rhs = rhs
            self.op = op
            self.name = f"{lhs} {op} {rhs}"

        def __str__(self) -> str:
            return self.name

        def rust(self):
            if self.op in ["+"]:
                return f"{self.lhs.rust()} {self.op} {self.rhs.rust()}"
            if self.op in ["=="]:
                return f"eq({self.lhs.rust()}, {self.rhs.rust()})"

    class Signal:
        def __init__(self, circuit, name: str, is_next: bool) -> None:
            self.circuit = circuit
            self.name = name
            self.value = []
            self.is_next = is_next

        def rust(self):
            if self.is_next:
                return f"{self.name}.next()"
            else:
                return f"{self.name}"

        def reset(self):
            self.value = []

        def undo(self):
            self.value.pop()

        def step(self):
            self.value.append(None)

        def assign(self, value):
            self.value[-1] = value

        def __add__(self, other):
            if type(other) in [int, bytes]:
                other = Circuit.Constant(self.circuit, other)
            return Circuit.Expression(self.circuit, self, other, '+')

        def __eq__(self, other) -> bool:
            if type(other) in [int, bytes]:
                other = Circuit.Constant(self.circuit, other)
            return Circuit.Expression(self.circuit, self, other, '==')

        def __str__(self) -> str:
            if self.is_next:
                return f"Sig({self.name}).next"
            return f"Sig({self.name})"

    class Constant:
        def __init__(self, circuit, value) -> None:
            self.circuit = circuit
            self.name = str(value)
            self.value = value

        def __str__(self) -> str:
            return f"Con({self.value})"

    class Constraint:
        def __init__(self, circuit, expression) -> None:
            self.circuit = circuit
            self.contrain = expression
            assert expression.op in ['==', '!=', '<', '>', '<=', '>=']

    class Step:
        def __init__(self, circuit, signals, is_next) -> None:
            self.signals = signals
            self.internal_signals = {}
            self.all_signals = {**signals}
            self.is_next = is_next
            for n, v in signals.items():
                setattr(self, n, v)
            self.circuit = circuit
            self.inited = True

        def internal_signal(self, name):
            assert not self.is_next
            assert type(name) is str
            tmp = Circuit.Signal(self.circuit, name, False)
            setattr(self, name, tmp)
            self.internal_signals[name] = tmp
            self.all_signals[name] = tmp
            self.circuit._add_internal_signal(tmp)
            tmp.step()

        def add_contrain(self, constrain):
            self.circuit.add_contrain(constrain)

        def add_transition(self, transition):
            self.circuit.add_transition(transition)

        def __setattr__(self, __name: str, __value: Any) -> None:
            if ('inited' in self.__dict__):
                if (__name in self.all_signals):
                    self.all_signals[__name].assign(__value)
                else:
                    super().__setattr__(__name, __value)
            super().__setattr__(__name, __value)

    def __init__(self, name) -> None:
        self.name = name
        self._forward_signal = {}
        self._forward_signal_next = {}
        self._step_types = {}
        self._trace = []
        self._internal_signal = []
        self._first_step = None
        self._last_step = None
        self._mode = 'dev'  # 'dev' or 'trace' or 'print'

    def add_contrain(self, constrain):
        self._trace[-1]['constrain'].append(constrain)

    def add_transition(self, transition):
        self._trace[-1]['transition'].append(transition)

    def forward_signal(self, name):
        assert type(name) is str
        assert self._mode == 'dev', f"Mode is not dev"

        sig = self.Signal(self, name, False)
        setattr(self, name, sig)
        self._forward_signal[name] = sig
        next_sig = self.Signal(self, name, True)
        self._forward_signal_next[name] = next_sig

    def _add_internal_signal(self, signal):
        assert type(signal) is Circuit.Signal, f"signal is not a Circuit.Signal"
        self._internal_signal[-1].append(signal)

    def set_first_step(self, step_function_name):
        assert step_function_name in self._step_types
        assert self._mode == 'dev', f"Mode is not dev"
        self._first_step = step_function_name

    def set_last_step(self, step_function_name):
        assert step_function_name in self._step_types
        assert self._mode == 'dev', f"Mode is not dev"
        self._last_step = step_function_name

    def step(self, step_function_name, witness_note):
        assert self._mode == 'trace', f"Mode is not trace"
        assert step_function_name in self._step_types, f"Step function {step_function_name} not defined"
        if len(self._trace) == 0:
            assert step_function_name == self._first_step, f"First step is not {self._first_step}"
        self._step(step_function_name, witness_note)

    def _step(self, step_function_name, witness_note):
        step = self.Step(self, self._forward_signal, False)
        next_step = self.Step(self, self._forward_signal_next, True)
        for sig in self._forward_signal.values():
            sig.step()
        for sig in self._forward_signal_next.values():
            sig.step()
        self._trace.append({})
        self._trace[-1]['name'] = step_function_name
        self._trace[-1]['constrain'] = []
        self._trace[-1]['transition'] = []
        self._internal_signal.append([])

        self._step_types[step_function_name]['cir'](step, next_step)
        self._step_types[step_function_name]['wg'](
            step, next_step, witness_note)

    def undo(self):
        self._trace.pop()
        self._internal_signal.pop()
        for sig in self._forward_signal.values():
            sig.undo()
        for sig in self._forward_signal_next.values():
            sig.undo()

    def def_step(self, name, step_function, step_function_wg):
        if self._mode == 'dev':
            assert name not in self._step_types
        self._step_types[name] = {"name": name,
                                  "cir": step_function, "wg": step_function_wg}
        step = self.Step(self, self._forward_signal, False)
        next_step = self.Step(self, self._forward_signal_next, True)
        for sig in self._forward_signal.values():
            sig.step()
        for sig in self._forward_signal_next.values():
            sig.step()
        self._trace.append({})
        self._trace[-1]['name'] = name
        self._trace[-1]['constrain'] = []
        self._trace[-1]['transition'] = []
        self._internal_signal.append([])
        step_function(step, next_step)
        self._step_types[name]["constrain"] = self._trace[-1]["constrain"]
        self._step_types[name]["internal_signal"] = self._internal_signal[-1]
        self._step_types[name]["transition"] = self._trace[-1]["transition"]

    def dev(self):
        self.reset()

    def trace(self):
        self.reset()
        self._mode = 'trace'

    def done(self):
        assert self._trace[-1]['name'] == self._last_step, f"Last step is not {self._last_step}"
        assert self._trace[-1]['transition'] == [], f"Last step has transition"
        self._mode = 'done'

    def reset(self):
        self._trace = []
        self._internal_signal = []
        for sig in self._forward_signal.values():
            sig.reset()
        self._mode = 'dev'

    def step_to_str(self, idx):
        tmp = [f"------ step {idx} ------"]
        tmp += [f"function: {self._trace[idx]['name']}"]
        if self._trace[idx]["constrain"]:
            tmp += ["constrain >"]
            for c in self._trace[idx]["constrain"]:
                tmp += [str(c)]

        if self._trace[idx]["transition"]:
            tmp += ["transition >"]
            for t in self._trace[idx]["transition"]:
                tmp += [str(t)]

        tmp += ["signal >", "forward signal >"]
        for sig in self._forward_signal.values():
            tmp += [f"{str(sig)} <== {sig.value[idx]}"]
        if self._internal_signal[idx]:
            tmp += ["internal signal"]
            for isig in self._internal_signal[idx]:
                tmp += [f"{isig} <== {isig.value[0]}"]

        tmp += [f"--- end of step {idx} ---"]
        return "\n".join(tmp)

    def __str__(self) -> str:

        tmp = [f">>>>>> Circuit {self.name} <<<<<<"]
        tmp += [f"\n>>> Forward Signal <<<"]

        tmp += [f"{k} <== {k.value}" for k in self._forward_signal.values()]
        tmp += [f"\n>>> Step Types <<<"]
        tmp += [f"{k}" for k in self._step_types.keys()]
        if self._trace:
            tmp += ["\n--- step trace ---"]
            for idx in range(len(self._trace)):
                tmp += [self.step_to_str(idx), ""]
        return "\n".join(tmp)


class Compiler:
    def __init__(self) -> None:
        pass

    @staticmethod
    def let_sig(sig):
        return f'\t\tlet {sig.name} = ctx.forward("{sig.name}");'

    @staticmethod
    def let_step(step):
        return f'\t\tlet {step["name"]} = ctx.step_type("{step["name"]}");'

    @staticmethod
    def create_wg(signals):
        code = [
            f'\t\t\tctx.wg(move | ctx, ({", ".join([f"{sig.name}_value" for sig in signals])}) | {{']
        code += [
            f"\t\t\t\tctx.assign({sig.name}, {sig.name}_value.field());" for sig in signals]
        code += ["\t\t\t});"]
        return "\n".join(code)

    @staticmethod
    def create_trace(circuit):
        code = ["\t\tctx.trace(move | ctx, _ | {"]
        tr = circuit._trace
        for idx in range(len(tr)):
            sig_val = [
                f"{sig.value[idx]}" for sig in circuit._forward_signal.values()]
            sig_val += [f"{isig.value[0]}" for isig in circuit._internal_signal[idx]]
            sig_val = ", ".join(sig_val)
            code += [f'\t\t\tctx.add( &{tr[idx]["name"]}, ({sig_val}));']
        code += ["\t\t})"]
        return "\n".join(code)

    @ staticmethod
    def step_type_def(step, circuit):
        print(step)
        code = [f'\n\t\t// {step["name"]}']
        code += [f'\t\tctx.step_type_def({step["name"]}, | ctx | {{']
        if step["internal_signal"]:
            code += [f'\t\t\t// add internal signal']
        code += [
            f'\t\t\tlet {sig.name} = ctx.internal("{sig.name}");' for sig in step["internal_signal"]]

        if step["constrain"]:
            code += [f'\n\t\t\t// add constrain']
        code += [f'\t\t\tctx.constr({exp.rust()});' for exp in step["constrain"]]

        if step["transition"]:
            code += [f'\n\t\t\t// add transition']
        code += [f'\t\t\tctx.transition({exp.rust()});' for exp in step["transition"]]

        code += [f'\t\t\t// def withness generator - do simple assignment - see python code for more detail']
        code += [Compiler.create_wg(list(circuit._forward_signal.values()) +
                                    step["internal_signal"])]
        code += ["\t\t});"]

        return "\n".join(code)

    def compile(self, circuit):

        assert circuit._mode == "done", "not done yet"

        code = [template.head]

        # circuit name
        code += [f"""fn {circuit.name}_circuit<F: FieldExt>() -> chiquito::ir::Circuit<F, (), (u64, u64, u64)> {{
\tlet {circuit.name} = circuit::<F, (), (u64, u64, u64), _>("{circuit.name}", |ctx| {{
\t\tuse chiquito::dsl::cb::*;"""]

        # signal and step
        code += ["\n\t\t// define signal"]
        code += [self.let_sig(sig) for sig in circuit._forward_signal.values()]
        code += ["\n\t\t// define step"]
        code += [self.let_step(step) for step in circuit._step_types.values()]
        code += ["\n\t\t// set first and last step"]
        code += [
            f"\t\tctx.pragma_first_step({circuit._first_step});",
            f"\t\tctx.pragma_last_step({circuit._last_step});"
        ]

        code += ["\n\t\t// define step type"]
        # define step
        code += [self.step_type_def(step, circuit)
                 for step in circuit._step_types.values()]

        code += ["\n\t\t// define trace"]
        code += [self.create_trace(circuit)]
        code += [f"\t}});",
                 f"\tlet compiler = Compiler::new(SingleRowCellManager {{}}, SimpleStepSelectorBuilder {{}});",
                 f"\tlet compiled = compiler.compile( &{circuit.name});",
                 "\tcompiled"
                 "}"]

        code += [template.tail]
        return "\n".join(code)
