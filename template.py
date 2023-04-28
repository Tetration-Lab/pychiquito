head = """
use chiquito::{
\tast::ToField,
\tbackend::halo2::{chiquito2Halo2, ChiquitoHalo2},
\tcompiler::{
\t\tcell_manager::SingleRowCellManager, step_selector::SimpleStepSelectorBuilder, Compiler,
\t},
\tdsl::circuit,
};
use halo2_proofs::{
\tcircuit::SimpleFloorPlanner,
\tdev::MockProver,
\thalo2curves::{bn256::Fr, FieldExt},
\tplonk::ConstraintSystem,
};
"""

tail = """
fn main() {
\tlet circuit = MagicCircuit {};

\tlet prover = MockProver::<Fr>::run(7, &circuit, Vec::new()).unwrap();

\tlet result = prover.verify_par();

\tprintln!("{:#?}", result);

\tif let Err(failures) = &result {
\t\tfor failure in failures.iter() {
\t\t\tprintln!("{}", failure);
\t\t}
\t}
}

// *** Halo2 boilerplate ***

#[derive(Clone)]
struct FiboConfig<F: FieldExt> {
\tcompiled: ChiquitoHalo2<F, (), (u64, u64, u64)>,
}

impl<F: FieldExt> FiboConfig<F> {
\tfn new(meta: &mut ConstraintSystem<F>) -> FiboConfig<F> {
\t\tlet mut compiled = chiquito2Halo2(fibo_circuit::<F>());

\t\tcompiled.configure(meta);

\t\tFiboConfig { compiled }
\t}
}

#[derive(Default)]
struct MagicCircuit {}

impl<F: FieldExt> halo2_proofs::plonk::Circuit<F> for MagicCircuit {
\ttype Config = FiboConfig<F>;

\ttype FloorPlanner = SimpleFloorPlanner;

\tfn without_witnesses(&self) -> Self {
\t\tSelf::default()
\t}

\tfn configure(meta: &mut halo2_proofs::plonk::ConstraintSystem<F>) -> Self::Config {
\t\tFiboConfig::<F>::new(meta)
\t}

\tfn synthesize(
\t\t&self,
\t\tconfig: Self::Config,
\t\tmut layouter: impl halo2_proofs::circuit::Layouter<F>,
\t) -> Result<(), halo2_proofs::plonk::Error> {
\t\tconfig.compiled.synthesize(&mut layouter, ());

\t\tOk(())
\t}
}
"""
