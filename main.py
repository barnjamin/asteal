import pyteal as pt 

def op_to_str(op: pt.Op):
    strop = str(op)
    match strop:
        case "concat":
            strop = "+"

    return strop

def expr_to_py(e: pt.Expr)->str:
    match e:
        case pt.LeafExpr():
            match e:
                case pt.Int():
                    return str(e.value)
                case pt.Bytes():
                    return e.byte_str

        case pt.BinaryExpr():
            return f"{expr_to_py(e.argLeft)} {op_to_str(e.op)} {expr_to_py(e.argRight)}"

        case pt.NaryExpr():
            return f" {op_to_str(e.op)} ".join([
                expr_to_py(arg)
                for arg in e.args
            ])

        case pt.UnaryExpr():
            return f"{op_to_str(e.op)}({expr_to_py(e.arg)})"

        case pt.Seq():
            return "\n".join([
                expr_to_py(arg)
                for arg in e.args
            ])
        case pt.Assert():
            return "\n".join([
                f"assert {expr_to_py(c)}"
                for c in e.cond
            ])
        case pt.ScratchStore():
            return f"{e.slot} = {expr_to_py(e.value)}"
        case pt.ScratchLoad():
            return expr_to_py(e.slot)
        case pt.For():
            start = expr_to_py(e.start)
            cond = expr_to_py(e.cond)
            step = expr_to_py(e.step)
            do = expr_to_py(e.doBlock)
            return f"""
{start}
while {cond}:
    {do}
    {step}
        """

        case _:
            return str(e)


progs: list[tuple[pt.Expr, str]] = [
    (
        pt.Int(10) + pt.Int(5), 
        """
10 + 5
        """
    ),
    (
        pt.Itob(pt.Int(10)), 
        """
itob(10)
        """
    ),
    (
        pt.Concat(pt.Bytes("hello ") , pt.Bytes("pyteal")), 
        """ 
"hello " + "pyteal" 
        """
    ),
    (
        pt.Seq(
            (x := pt.ScratchVar()).store(pt.Int(2)),
            x.load() + pt.Int(2)
        ),
        """
x = 2
x + 2
        """
    ),
    (
        pt.Seq(
            (x := pt.ScratchVar()).store(pt.Int(5)),
            pt.Assert(x.load()<pt.Int(10), x.load() == x.load()),
            pt.Assert(x.load()>pt.Int(1))
        ),
        """
x = 5
assert x < 10
assert x == x
assert x > 1 
        """
    ),
    (
        pt.For(
            (i := pt.ScratchVar()).store(pt.Int(0)),
            i.load() < pt.Int(10),
            i.store(i.load() + pt.Int(1))
        ).Do(
            pt.Assert(i.load() < pt.Int(10))
        ),
        """
x = 0
while x < 10:
    assert x < 10
    x = x + 1
        """
    ),

]


for prog in progs:
    print(expr_to_py(prog[0]))
    print()
    print(prog[1].strip())
    print("----")


