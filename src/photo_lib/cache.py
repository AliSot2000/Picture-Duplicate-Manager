from collections.abc import Hashable
from typing import Any

import numpy as np

from custom_enum import TargetViewTable
from photo_lib.data_objects import MediaElement


class NotDefined(object):
    """
    NotDefined function to allow None results to be cached as well
    """
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NotDefined, cls).__new__(cls)
        return cls.instance


nd = NotDefined()


class Cache:
    __max_size: int

    _arg_res_lookup: dict
    _arg_index_lookup: dict
    _index_arg_lookup: dict

    _lru: np.ndarray[bool]
    _lru_index: int

    __hits: int = 0
    __misses: int = 0

    @property
    def size(self):
        return self.__max_size

    @property
    def current_size(self):
        return len(self._arg_res_lookup.keys())

    @property
    def hits(self):
        return self.__hits

    @property
    def misses(self):
        return self.__misses

    def get_stats(self):
        """
        Get cache statistics
        """
        return {"max_size": self.size, "hits": self.__hits, "misses": self.__misses, "current_size": self.current_size}

    def __init__(self, size: int = 128):
        """
        Parameter Size is afterwards a read only attribute.
        """
        self.__max_size = size
        self._lru_index = 0
        self._lru = np.array([False for _ in range(self.size)])

        # Need to explicitly set it here, otherwise, clashes bc of class vars.
        self._arg_res_lookup = {}
        self._arg_index_lookup = {}
        self._index_arg_lookup = {}

    def get(self, arg: Hashable):
        """
        Query the Cache to see, if we have the value cached.
        """
        if arg is nd:
            raise ValueError("nd may not be used as argument or value in the Cache.")

        res = self._arg_res_lookup.get(arg, nd)
        if res is nd:
            self.__misses += 1
            return nd

        else:
            self.__hits += 1
            # Set the hit flag
            self._lru[self._arg_index_lookup[arg]] = True
            return res

    def set(self, arg: Hashable, value: Any):
        """
        Set the value of a given argument.
        """
        if arg is nd or value is nd:
            raise ValueError("nd may not be used as argument or value in the Cache.")

        res = self._arg_res_lookup.get(arg, nd)

        # Cache hit, update the flag
        if res is not nd:
            self._lru[self._arg_index_lookup[arg]] = True
            self._arg_res_lookup[arg] = value

        # The argument isn't currently in the cache.
        else:
            # The cache hasn't reached full size, just add the new value
            if len(self._arg_res_lookup) < self.size:

                # Find the entry in the index to arg lookup which currently doesn't have a value set.
                idx = 0
                while idx < self.size and self._index_arg_lookup.get(idx, nd) is not nd:
                    idx += 1

                assert self._lru[idx] == False, "Unexpected LRU state."

                # Store the argument in the argument to result lookup dict
                self._arg_res_lookup[arg] = value

                # Store the index in the __lru array in the arg to index lookup dict
                self._arg_index_lookup[arg] = idx

                # Store the index to argument lookup (needed for eviction)
                self._index_arg_lookup[idx] = arg

                # Set the entry as accessed
                self._lru[self._arg_index_lookup[arg]] = True

                # Return, we don't want to update anything else
                return

            else:
                assert len(self._arg_res_lookup) == self.size, (f"Unexpected size of cache: "
                                                                  f"{len(self._arg_res_lookup)}, "
                                                                  f"max_size: {self.size}")
                # Find the index to evict
                while self._lru[self._lru_index]:
                    # Update the flag
                    self._lru[self._lru_index] = False

                    # increment the pointer
                    self._lru_index = (self._lru_index + 1) % self.size

                assert self._lru[self._lru_index] == False, "Unexpected outcome of find evict"

                # Get the argument to evict
                old_arg = self._index_arg_lookup[self._lru_index]

                del self._arg_index_lookup[old_arg]
                del self._arg_res_lookup[old_arg]

                # Set the new lookup target
                self._index_arg_lookup[self._lru_index] = arg

                # Set the accessed flag
                self._lru[self._lru_index] = True

                # Store arg to x lookups.
                self._arg_res_lookup[arg] = value
                self._arg_index_lookup[arg] = self._lru_index

    def update(self, arg: Hashable, value: Any):
        """
        Update a result in the cache, provided the argument is cached.
        """
        if arg is nd or value is nd:
            raise ValueError("nd may not be used as argument or value in the Cache.")

        res = self._arg_res_lookup.get(arg, nd)
        if res is nd:
            return

        # Only update the arg
        self._arg_res_lookup[arg] = value

    def evict(self, arg: Hashable) -> bool:
        """
        Evict a value from the cache, provided it is there.
        """
        if arg is nd:
            raise ValueError("nd may not be used as argument or value in the Cache.")

        res = self._arg_res_lookup.get(arg, nd)
        if res is nd:
            return False

        # PRECONDITION: Argument is in cache
        # Set the cache to be populate
        self._lru[self._arg_index_lookup[arg]] = False

        # Remove the lookup from index to argument
        del self._index_arg_lookup[self._arg_index_lookup[arg]]

        # Finally, clearing the arg to x lookups
        del self._arg_res_lookup[arg]
        del self._arg_index_lookup[arg]
        return True

    def inspect(self):
        """
        Inspect the cache
        """
        print(self._arg_res_lookup)
        print(self._arg_index_lookup)
        print(self._index_arg_lookup)
        print(self._lru)

    def reset(self):
        """
        Reset entire cache. Not all cache updates are efficient. In cases where updates are rare and expensive,
        it is easier to clear the cache instead.
        """
        self._arg_res_lookup: dict = {}
        self._arg_index_lookup: dict = {}
        self._index_arg_lookup: dict = {}

        self._lru_index = 0
        self._lru = np.array([False for _ in range(self.size)])

        self.__hits: int = 0
        self.__misses: int = 0


class MediaCache(Cache):
    """
    This Cache is specifically made for the MediaPaths objects. In this case, we need to be able to evict elements from
    cache based on the table they are a part of. For this, we introduce a new function - evict partition
    """
    def evict_partition(self, partition: TargetViewTable):
        """
        Evict all elements which share the partition.
        """
        for key in self._arg_res_lookup.keys():
            assert isinstance(key, MediaElement), "Unexpected key type for MediaCache"

            # Remove the element from cache if we have a match.
            if key.source_table == partition:
                self.evict(key)


if __name__ == "__main__":  # pragma: no cover
    test_cache = Cache(size=4)

    test_cache.set(1, "one")
    test_cache.set(2, "two")
    test_cache.set(3, "three")
    test_cache.set(4, "four")

    test_cache.inspect()

    # Should unset 1
    test_cache.set(5, "five")
    test_cache.inspect()

    test_cache.get(3)
    test_cache.get(4)

    # Should evict 2
    test_cache.set(6, "six")
    test_cache.inspect()

    # Should evict 5
    test_cache.set(7, "seven")
    test_cache.inspect()

    test_cache.evict(3)
    test_cache.inspect()

    test_cache.set(8, "eight")
    test_cache.inspect()

    print(test_cache.get_stats())

    test_cache.reset()
    print(test_cache.get_stats())
