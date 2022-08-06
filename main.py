import pyteal as pt
import pyteal.ast.substring as substr
import pyteal.ast.return_ as ret
import pyteal.ast.itxn as itxn
from c2c import approval, clear

# Dumb program to write out python given a pyteal expression
# might be helpful later going from python => pyteal

# TODO: cant figure out how to get variable names


class Converter:
    def __init__(self, e: pt.Expr):
        self.subroutine_list: list[pt.SubroutineDefinition] = []
        self.body = self.expr_to_py(e)

        self.subroutines = {
            subr.name(): Converter(subr.declaration) for subr in self.subroutine_list
        }

    def __str__(self) -> str:
        body = [subr.body for subr in self.subroutines.values()]

        return "\n\n".join(body + [self.body])

    def op_to_str(self, op: pt.Op) -> str:
        strop = str(op)
        match strop:
            case "concat":
                strop = "+"
        return strop

    def expr_to_py(self, e: pt.Expr, indent: int = 0) -> str:
        py = ""
        match e:
            case pt.SubroutineDeclaration():
                return f"""def {e.subroutine.name()}({",".join(e.subroutine.arguments())}):\n\t{self.expr_to_py(e.body)}"""
            case pt.LeafExpr():
                match e:
                    case pt.Int():
                        py = str(e.value)
                    case pt.Bytes():
                        py = '"' + e.byte_str + '"'
                    case pt.TxnExpr():
                        py = f"{str(e.op)}[{e.field.name}]"
                    case pt.TxnaExpr():
                        py = f"{str(e.dynamicOp)}[{e.field.name}][{e.index}]"
                    case pt.EnumInt():
                        py = e.name
                    case pt.Global():
                        py = e.field.name
                    case pt.MethodSignature():
                        py = f"""method_signature("{e.methodName}")"""
                return py

            case pt.BinaryExpr():
                py = f"{self.expr_to_py(e.argLeft)} {self.op_to_str(e.op)} {self.expr_to_py(e.argRight)}"

            case pt.NaryExpr():
                py = f" {self.op_to_str(e.op)} ".join(
                    [self.expr_to_py(arg) for arg in e.args]
                )

            case pt.UnaryExpr():
                # unary exprs should be available as standalone methods
                py = f"{self.op_to_str(e.op)}({self.expr_to_py(e.arg)})"

            case pt.Seq():
                py = "\n".join([self.expr_to_py(arg) for arg in e.args])

            case pt.Assert():
                py = "\n".join([f"assert {self.expr_to_py(c)}" for c in e.cond])

            case pt.ScratchStore():
                py = f"{e.slot} = {self.expr_to_py(e.value)}"

            case pt.ScratchLoad():
                py = self.expr_to_py(e.slot)

            case pt.For():
                start = self.expr_to_py(e.start)
                cond = self.expr_to_py(e.cond)
                step = self.expr_to_py(e.step)
                do = self.expr_to_py(e.doBlock)
                py = f"""
    {start}
    while {cond}:
        {do}
        {step}
            """

            case pt.Cond():
                argd = [
                    f"if {self.expr_to_py(arg[0])}:\n{self.expr_to_py(arg[1], indent+1)}"
                    for arg in e.args
                ]

                py = "\nel".join(argd)

            case pt.Return():
                py = f"return {self.expr_to_py(e.value)}"

            case pt.SubroutineCall():
                decl = e.subroutine.get_declaration()
                self.subroutine_list.append(decl.subroutine)
                args = [self.expr_to_py(arg) for arg in e.args]
                py = f"""{decl.subroutine.name()}({",".join(args)})"""

            case pt.ScratchSlot():
                py = str(e.id)

            case pt.ScratchStackStore():
                py = f"{e.slot} = ^^  "

            case substr.SuffixExpr():
                py = f"suffix({self.expr_to_py(e.stringArg)}, {self.expr_to_py(e.startArg)})"

            case substr.ExtractExpr():
                py = f"extract({self.expr_to_py(e.stringArg)}, {self.expr_to_py(e.startArg)}, {self.expr_to_py(e.lenArg)})"

            case ret.ExitProgram():
                py = "return 0"

            case itxn.InnerTxnActionExpr():
                py = f"InnerTxn.{str(e.action.name)}()"

            case itxn.InnerTxnFieldExpr():
                py = (
                    f"InnerTxnField.{str(e.field.arg_name)}({self.expr_to_py(e.value)})"
                )

            case _:
                print(e.__class__)
                py = str(e)

        return "\t" * indent + py


progs: list[tuple[pt.Expr, str]] = [
    (
        pt.Int(10) + pt.Int(5),
        """
10 + 5
        """,
    ),
    (
        pt.Itob(pt.Int(10)),
        """
itob(10)
        """,
    ),
    (
        pt.Concat(pt.Bytes("hello "), pt.Bytes("pyteal")),
        """ 
"hello " + "pyteal" 
        """,
    ),
    (
        pt.Seq((x := pt.ScratchVar()).store(pt.Int(2)), x.load() + pt.Int(2)),
        """
x = 2
x + 2
        """,
    ),
    (
        pt.Seq(
            (x := pt.ScratchVar()).store(pt.Int(5)),
            pt.Assert(x.load() < pt.Int(10), x.load() == x.load()),
            pt.Assert(x.load() > pt.Int(1)),
        ),
        """
x = 5
assert x < 10
assert x == x
assert x > 1 
        """,
    ),
    (
        pt.For(
            (x := pt.ScratchVar()).store(pt.Int(0)),
            x.load() < pt.Int(10),
            x.store(x.load() + pt.Int(1)),
        ).Do(pt.Assert(x.load() < pt.Int(10))),
        """
x = 0
while x < 10:
    assert x < 10
    x = x + 1
        """,
    ),
    (approval(), """ """),
]


for prog in progs:
    c = Converter(prog[0])
    print(c)
    # print(c.body)
    # print(prog[1].strip())
    print("----")
