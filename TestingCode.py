import asyncio

from guardrails.errors import ValidationError
from guardrails.hub import ProfanityFree
from guardrails import AsyncGuard


async def main():
    # Crea l'istanza di AsyncGuard e aggiungi il validator
    guard = AsyncGuard(id="asyncProfCheck", name="ProfanityCheck").use(
        ProfanityFree, on_fail="exception"
    )

    # Test: validazione che passa
    result_valid = await guard.validate(
        """
        Director Denis Villeneuve's Dune is a visually stunning and epic adaptation 
        of the classic science fiction novel. 
        It is reminiscent of the original Star Wars trilogy, with its grand scale and epic storytelling.
        """
    )
    print("Passing result:", result_valid)

    # Test: validazione che fallisce
    try:
        result_invalid=await guard.validate(
            """
            He is such a dickhead and a fucking idiot.
            """
        )
        print("Failing result:", result_invalid)
    except ValidationError as e:
        print("Validation failed:", e)



if __name__ == "__main__":
    asyncio.run(main())
