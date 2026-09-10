# License FAQ

### Can you summarize what Companion OMI's license allows?

The license grants free rights to use, modify, and redistribute Companion OMI source code for personal or nonprofit purposes. The intent is to stay permissive for those uses while limiting commercial abuse of Companion Intelligence products.

Companion OMI is Companion Intelligence's integration for the [Omi](https://www.omi.me/) wearable capture device — it streams audio and activity data from Omi hardware to Companion Memory (CI-Server) over Bluetooth, and bundles Omi's own client SDKs for building Omi-connected apps.

Companion OMI uses the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0). The full text is in [`LICENSE.md`](../LICENSE.md).

### What freedoms do you have as a Companion OMI user?

If you use Companion OMI for personal or nonprofit purposes, you can view, modify, and redistribute the source under the same license terms, subject to the PolyForm Noncommercial restrictions.

### Can I fork Companion OMI?

Yes. For noncommercial use, you can fork, modify, and redistribute Companion OMI under the same license.

### Can I contribute to Companion OMI?

Yes. Open a pull request on this repository.

### Can I sell Companion OMI?

No. Selling Companion OMI, including cloud-hosted instances, appliances that ship it, or paid support for those products, is not permitted. For commercial partnership questions, email partner@companionintelligence.com.

### What about the vendored Omi SDKs under `sdks/`?

`sdks/react-native`, `sdks/python`, and `sdks/swift` are [BasedHardware's](https://github.com/BasedHardware/omi) own Omi client SDKs, included here so Companion OMI can talk to Omi hardware. Each keeps its own upstream **MIT license**, as declared in its own `package.json` or podspec — that doesn't change with this license switch. The PolyForm Noncommercial terms in `LICENSE.md` cover Companion OMI's own integration code (`backend/`, `scripts/`, etc.), not BasedHardware's copyright in the vendored SDKs.

### Does this license apply to the rest of Companion Intelligence?

Companion Portal stays a separate commercial product — this license does not apply to it.

Companion Hub, Companion Memory, Companion Marketplace, Companion OS, Companion Capture, Companion Browser Extension, Companion Mentra, Companion Even Realities, Companion Pebble, and Companion Home Assistant Voice PE use the same PolyForm Noncommercial terms in their own repositories.

Companion Pipe and Companion MaixCAM are still under legal review for third-party licensing terms in code they bundle — don't assume they're covered by this FAQ until that review lands.

### Unsure whether your use case is allowed?

Email support@companionintelligence.com.
