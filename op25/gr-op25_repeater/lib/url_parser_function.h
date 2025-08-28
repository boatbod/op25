#pragma once

#include <string>
#include <cstring>

class URLParserFunction
{
public:
	static bool FindKeyword(const std::string& input_url, size_t& st, size_t& before, const std::string& delim, std::string& result)
	{
		st = input_url.find(delim, before);
		if (st == std::string::npos)
		{
            result = input_url.substr(before, input_url.length() - before);
            st = input_url.length();
			return false;
		}

        result = input_url.substr(before, st - before);
		before = st + delim.length();

		if (result.empty())
			return false;

		return true;
	};

	static bool SplitQueryString(const std::string& str, const std::string& delim, std::string& key, std::string& value)
	{
		size_t st = str.find(delim, 0);

        key = str.substr(0, st);
        value = str.substr(st + 1, str.length() - st);

		return true;
	};
};
