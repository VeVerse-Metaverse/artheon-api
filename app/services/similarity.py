from strsimpy import NormalizedLevenshtein
from strsimpy.jaro_winkler import JaroWinkler


class Service:

    def get_similarity_score_jw(self, left: str, right: str):
        jw = JaroWinkler()
        return jw.similarity(left, right)

    def get_similarity_score_nl(self, left: str, right: str):
        normalized_levenshtein = NormalizedLevenshtein()
        return normalized_levenshtein.similarity(left, right)

    def get_distance_score_jw(self, left: str, right: str):
        jw = JaroWinkler()
        return jw.distance(left, right)

    def get_distance_score_nl(self, left: str, right: str):
        normalized_levenshtein = NormalizedLevenshtein()
        return normalized_levenshtein.distance(left, right)


if __name__ == '__main__':
    srv = Service()

    left = "oil on canvas"
    right = "oil"
    print()
    print("similarity:", srv.get_similarity_score_jw(left, right))
    print("distance:", srv.get_distance_score_jw(left, right))
    print()
    print("similarity:", srv.get_similarity_score_nl(left, right))
    print("distance:", srv.get_distance_score_nl(left, right))
