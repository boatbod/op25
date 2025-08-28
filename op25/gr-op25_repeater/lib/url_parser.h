//
// URL Parser for C++
// Created Oct 22, 2017.
// Website : https://github.com/dongbum/URLParser
// Usage : Just include this header file.
//
// Corrected and converted to C++11, August 27, 2025
// (C) gnorbury@bondcar.com

#pragma once

#include <string>
#include <vector>
#include <unordered_map>

#include "url_parser_function.h"

class URLParser
{
public:
	struct HTTP_URL
	{
		std::string scheme;
		std::string host;
		std::string port;
		std::vector<std::string> path;
		std::string query_string;
		std::unordered_map<std::string, std::string> query;
	};

public:
	static HTTP_URL Parse(const std::string& input_url)
	{
		HTTP_URL http_url;

		size_t st = 0;
		size_t before = 0;

		if (!URLParserFunction::FindKeyword(input_url, st, before, "://", http_url.scheme))
        {
            http_url.scheme.clear();
            return http_url; //stop decode if scheme is missing
        }

		bool has_path   = URLParserFunction::FindKeyword(input_url, st, before, "/", http_url.host);

		size_t temp_st = 0;
		size_t temp_before = 0;
		std::string temp_ip;
		std::string temp_port;

		if (true == URLParserFunction::FindKeyword(http_url.host, temp_st, temp_before, ":", temp_ip))
		{
			http_url.port = std::string(&http_url.host[temp_before]);
			http_url.host = temp_ip;
		}

        if (!has_path)
            return http_url;

        std::string full_path;
        bool has_query = URLParserFunction::FindKeyword(input_url, st, before, "?", full_path);
        temp_st = st;
        temp_before = before;
        st = 0;
        before = 0;
		while (true)
		{
			std::string path;
			bool rc = URLParserFunction::FindKeyword(full_path, st, before, "/", path);
            if (!path.empty())
			    http_url.path.push_back(path);
            
			if (rc == false)
				break;
		}
        st = temp_st;
        if (!has_query)
            return http_url;

		if (st < input_url.length())
		{
			http_url.query_string = std::string(&input_url[st + 1]);
			if (false == http_url.query_string.empty())
			{
				std::string query;
				st = 0;
				before = 0;

				while (true)
				{
					std::string key, value;

					if (false == URLParserFunction::FindKeyword(http_url.query_string, st, before, "&", query))
					{
						URLParserFunction::SplitQueryString(std::string(&http_url.query_string[before]), "=", key, value);
						http_url.query.insert(std::unordered_map<std::string, std::string>::value_type(key, value));
						break;
					}

					URLParserFunction::SplitQueryString(query, "=", key, value);
					http_url.query.insert(std::unordered_map<std::string, std::string>::value_type(key, value));
				}
			}
		}

		return http_url;
	};
};
