#include "abgleich.h"

#include <cctype>
#include <set>

namespace kz {

namespace {

std::string klein(const std::string& s) {
    std::string aus = s;
    for (auto& c : aus) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return aus;
}

}  // namespace

Plan plane_abgleich(const Stand& neu, const std::function<bool(const std::string& sha)>& vorhanden) {
    Plan p;
    std::set<std::string> gesehen;
    for (const auto& d : neu.dateien) {
        std::string sha = klein(d.sha256);
        if (!gesehen.insert(sha).second) continue;
        if (vorhanden(sha)) continue;
        p.laden.push_back(d);
        p.bytes += d.bytes;
    }
    return p;
}

std::vector<std::string> ueberfluessig(const Stand& neu, const std::vector<std::string>& vorhandene) {
    std::set<std::string> gebraucht;
    for (const auto& d : neu.dateien) gebraucht.insert(klein(d.sha256));
    std::vector<std::string> weg;
    for (const auto& sha : vorhandene)
        if (gebraucht.count(klein(sha)) == 0) weg.push_back(sha);
    return weg;
}

bool sha_gleich(const std::string& a, const std::string& b) {
    return a.size() == b.size() && klein(a) == klein(b);
}

std::string dateiname(const std::string& sha) {
    return klein(sha) + ".wav";
}

}  // namespace kz
