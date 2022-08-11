import pyteal as pt
import pyteal.ast.substring as substr
import pyteal.ast.return_ as ret
import pyteal.ast.itxn as itxn
from c2c import approval

# Dumb program to write out python given a pyteal expression
# might be helpful later going from python => pyteal

# TODO: figure out how to get variable names
# TODO: instead of returning a string, return the python AST elements
# TODO: use IR instead of Exprs

class ExprConverter:
    def __init__(self, e: pt.Expr):
        self.subroutine_list: list[pt.SubroutineDefinition] = []

        self.body = self.expr_to_py(e)

        self.subroutines = {
            subr.name(): ExprConverter(subr.declaration)
            for subr in self.subroutine_list
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
                return f"""def {e.subroutine.name()}({",".join(e.subroutine.arguments())}):\n{self.expr_to_py(e.body, indent+1)}"""
            case pt.LeafExpr():
                match e:
                    case pt.Int():
                        py = str(e.value)
                    case pt.Bytes():
                        py = '"' + e.byte_str + '"'
                    case pt.TxnExpr():
                        py = f"{str(e.op)}[{e.field.name}]"
                    case pt.TxnaExpr():
                        idx = str(e.index)
                        if type(e.index) is not int:
                            idx = self.expr_to_py(e.index)

                        py = f"{str(e.dynamicOp)}[{e.field.name}][{idx}]"
                    case pt.EnumInt():
                        py = e.name
                    case pt.Global():
                        py = e.field.name
                    case pt.MethodSignature():
                        py = f"""method_signature("{e.methodName}")"""
                #return py

            case pt.BinaryExpr():
                py = f"{self.expr_to_py(e.argLeft)} {self.op_to_str(e.op)} {self.expr_to_py(e.argRight)}"

            case pt.NaryExpr():
                py = f" {self.op_to_str(e.op)} ".join(
                    [self.expr_to_py(arg) for arg in e.args]
                )

            case pt.UnaryExpr():
                py = f"pt.{self.op_to_str(e.op)}({self.expr_to_py(e.arg)})"

            case pt.Seq():
                # if len(e.args)>1:
                #     return "\n".join([self.expr_to_py(arg, indent) for arg in e.args[:-1]])+f"\n\treturn {self.expr_to_py(e.args[-1], indent)}"
                # else:
                return "\n".join([self.expr_to_py(arg, indent) for arg in e.args])

            case pt.Assert():
                py = "\n".join([f"assert {self.expr_to_py(c, indent)}" for c in e.cond])

            case pt.ScratchStore():
                py = f"{e.slot} = {self.expr_to_py(e.value)}"

            case pt.ScratchLoad():
                py = self.expr_to_py(e.slot)

            case pt.For():
                start = self.expr_to_py(e.start, indent)
                cond = self.expr_to_py(e.cond, indent)
                step = self.expr_to_py(e.step, indent + 1)
                do = self.expr_to_py(e.doBlock, indent + 1)
                py = f"""{start}\nwhile {cond}:\n{do}\n{step}"""

            case pt.Cond():
                argd = [
                    f"if {self.expr_to_py(arg[0])}:\n{self.expr_to_py(arg[1], indent+1)}"
                    for arg in e.args
                ]

                py = "\nel".join(argd)

            case pt.Return():
                py = f"{self.expr_to_py(e.value)}"

            case pt.SubroutineCall():
                decl = e.subroutine.get_declaration()
                self.subroutine_list.append(decl.subroutine)
                args = [self.expr_to_py(arg) for arg in e.args]
                py = f"""{decl.subroutine.name()}({",".join(args)})"""

            case pt.ScratchSlot():
                py = f"slot#{str(e.id)}"

            case pt.ScratchStackStore():
                py = f"{e.slot} = ^^"

            case substr.SuffixExpr():
                py = f"pt.suffix({self.expr_to_py(e.stringArg)}, {self.expr_to_py(e.startArg)})"

            case substr.ExtractExpr():
                py = f"pt.extract({self.expr_to_py(e.stringArg)}, {self.expr_to_py(e.startArg)}, {self.expr_to_py(e.lenArg)})"

            case ret.ExitProgram():
                py = "0"

            case itxn.InnerTxnActionExpr():
                py = f"pt.InnerTxn.{str(e.action.name)}()"

            case itxn.InnerTxnFieldExpr():
                py = f"pt.InnerTxnField.{str(e.field.arg_name)}({self.expr_to_py(e.value)})"

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
    c = ExprConverter(prog[0])
    print(c)
    print()
    print(prog[1].strip())
    print("----")
