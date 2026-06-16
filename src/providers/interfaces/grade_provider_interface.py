from abc import ABC, abstractmethod
from src.models.schemas import Grade


class GradeProviderInterface(ABC):

    @abstractmethod
    def listar_grades(self) -> list[Grade]: ...

    @abstractmethod
    def buscar_grade(self, grade_id: str) -> Grade | None: ...
